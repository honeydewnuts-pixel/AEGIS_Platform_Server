//+------------------------------------------------------------------+
//| AEGIS_OHLC_Feed.mq5                                              |
//| Independent OHLC stream for AEGIS (not tied to phone screenshots)|
//| Attach to any chart. Sends CopyRates history to the API.         |
//| Inputs:                                                          |
//|   InpServerUrl = https://YOUR-AEGIS-API.onrender.com             |
//|   InpApiKey    = mobile/account API key                          |
//|   InpAccountId = ACC-...                                         |
//|   InpBars      = 200                                             |
//| Enable WebRequest for the server URL in Tools → Options → Expert |
//+------------------------------------------------------------------+
#property copyright "Honeydewnuts Nigerian Limited / LeverageFx"
#property version   "1.00"
#property strict

input string InpServerUrl = "https://aegis-api-0z1p.onrender.com";
input string InpApiKey    = "";
input string InpAccountId = "";
input int    InpBars      = 200;
input int    InpTimerSec  = 30;   // poll interval; also fires on new bar

datetime g_last_bar_time = 0;

string TfString()
{
   ENUM_TIMEFRAMES tf = Period();
   if(tf == PERIOD_M1)  return "M1";
   if(tf == PERIOD_M5)  return "M5";
   if(tf == PERIOD_M15) return "M15";
   if(tf == PERIOD_M30) return "M30";
   if(tf == PERIOD_H1)  return "H1";
   if(tf == PERIOD_H4)  return "H4";
   if(tf == PERIOD_D1)  return "D1";
   return "M5";
}

string JsonEscape(string s)
{
   string o = s;
   StringReplace(o, "\\", "\\\\");
   StringReplace(o, "\"", "\\\"");
   return o;
}

bool PostOhlc()
{
   if(StringLen(InpApiKey) < 8)
   {
      Print("AEGIS OHLC: set InpApiKey");
      return false;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int n = CopyRates(_Symbol, Period(), 0, InpBars, rates);
   if(n < 5)
   {
      Print("AEGIS OHLC: CopyRates failed n=", n);
      return false;
   }

   // rates[0] = current forming bar; rates[1] = last closed
   string bars = "[";
   // send chronological order (oldest first) for server
   for(int i = n - 1; i >= 0; i--)
   {
      string status = (i == 0) ? "CURRENT" : "CLOSED";
      if(i < n - 1) bars += ",";
      bars += StringFormat(
         "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"tick_volume\":%d,\"spread\":%d,\"bar_status\":\"%s\"}",
         (int)rates[i].time,
         rates[i].open, rates[i].high, rates[i].low, rates[i].close,
         (int)rates[i].tick_volume, (int)rates[i].spread, status
      );
   }
   bars += "]";

   // rates[0]=CURRENT forming, rates[1]=last CLOSED
   string cur = StringFormat(
      "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"tick_volume\":%d,\"spread\":%d,\"bar_status\":\"CURRENT\"}",
      (int)rates[0].time, rates[0].open, rates[0].high, rates[0].low, rates[0].close,
      (int)rates[0].tick_volume, (int)rates[0].spread
   );
   string closed = cur;
   if(n >= 2)
      closed = StringFormat(
         "{\"time\":%d,\"open\":%.5f,\"high\":%.5f,\"low\":%.5f,\"close\":%.5f,\"tick_volume\":%d,\"spread\":%d,\"bar_status\":\"CLOSED\"}",
         (int)rates[1].time, rates[1].open, rates[1].high, rates[1].low, rates[1].close,
         (int)rates[1].tick_volume, (int)rates[1].spread
      );

   string body = StringFormat(
      "{\"account_id\":\"%s\",\"symbol\":\"%s\",\"timeframe\":\"%s\",\"source\":\"mt5_ea\",\"bars\":%s,\"current_bar\":%s,\"closed_bar\":%s}",
      JsonEscape(InpAccountId),
      JsonEscape(_Symbol),
      TfString(),
      bars,
      cur,
      closed
   );

   string url = InpServerUrl;
   if(StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   url += "/api/mt5/ohlc/stream";

   char post[];
   char result[];
   string headers = "Content-Type: application/json\r\nX-API-Key: " + InpApiKey + "\r\n";
   StringToCharArray(body, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post) - 1); // drop null

   string result_headers;
   int code = WebRequest("POST", url, headers, 15000, post, result, result_headers);
   if(code == -1)
   {
      Print("AEGIS OHLC: WebRequest failed. Add URL to Expert Advisors allow list: ", InpServerUrl);
      return false;
   }
   Print("AEGIS OHLC: HTTP ", code, " bars=", n, " symbol=", _Symbol);
   return (code >= 200 && code < 300);
}

void OnInit()
{
   EventSetTimer(InpTimerSec);
   PostOhlc();
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   PostOhlc();
}

void OnTick()
{
   datetime t = iTime(_Symbol, Period(), 0);
   if(t != g_last_bar_time)
   {
      g_last_bar_time = t;
      PostOhlc();
   }
}
