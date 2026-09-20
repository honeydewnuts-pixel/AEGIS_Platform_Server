//+------------------------------------------------------------------+
//| AEGIS_OHLC_Feed.mq5  v2.00                                       |
//| ChartOnly: streams _Symbol (V1 behaviour).                       |
//| MultiSymbol: streams SymbolsList (or empty = Market Watch used). |
//| Same /api/mt5/ohlc/stream endpoint; one POST per symbol.         |
//| CLOSED vs CURRENT bars preserved. No invented OHLC.              |
//+------------------------------------------------------------------+
#property copyright "Honeydewnuts Nigerian Limited / LeverageFx"
#property version   "2.00"
#property strict
#property description "AEGIS multi-symbol OHLC feed for broker-direct market data"

enum ENUM_AEGIS_FEED_MODE
  {
   FEED_MODE_CHART_ONLY  = 0,
   FEED_MODE_MULTI_SYMBOL = 1
  };

input string InpServerUrl   = "https://aegis-api-0z1p.onrender.com";
input string InpApiKey      = "";
input string InpAccountId   = "";
input ENUM_AEGIS_FEED_MODE InpMode = FEED_MODE_CHART_ONLY;
input string InpSymbolsList = "";   // Multi: "GBPUSD,EURUSD,USDJPY" empty=Market Watch (FX-like)
input int    InpBars        = 200;
input int    InpTimerSec    = 30;
input int    InpMaxSymbols  = 24;
input ENUM_TIMEFRAMES InpForceTF = PERIOD_CURRENT; // CURRENT = chart TF; or force M5 etc.

datetime g_last_bar_time[];  // parallel to symbol list
string   g_symbols[];

//+------------------------------------------------------------------+
string TfString(ENUM_TIMEFRAMES tf)
  {
   if(tf == PERIOD_CURRENT) tf = Period();
   if(tf == PERIOD_M1)  return "M1";
   if(tf == PERIOD_M5)  return "M5";
   if(tf == PERIOD_M15) return "M15";
   if(tf == PERIOD_M30) return "M30";
   if(tf == PERIOD_H1)  return "H1";
   if(tf == PERIOD_H4)  return "H4";
   if(tf == PERIOD_D1)  return "D1";
   return "M5";
  }

ENUM_TIMEFRAMES ActiveTF()
  {
   if(InpForceTF == PERIOD_CURRENT) return Period();
   return InpForceTF;
  }

string JsonEscape(string s)
  {
   string o = s;
   StringReplace(o, "\\", "\\\\");
   StringReplace(o, "\"", "\\\"");
   return o;
  }

string BaseUrl()
  {
   string url = InpServerUrl;
   if(StringLen(url) > 0 && StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   return url;
  }

string NormalizeBase(string sym)
  {
   string s = sym;
   int d = StringFind(s, ".");
   if(d > 0) s = StringSubstr(s, 0, d);
   StringToUpper(s);
   return s;
  }

//+------------------------------------------------------------------+
void BuildSymbolList()
  {
   ArrayResize(g_symbols, 0);
   if(InpMode == FEED_MODE_CHART_ONLY)
     {
      ArrayResize(g_symbols, 1);
      g_symbols[0] = _Symbol;
     }
   else if(StringLen(InpSymbolsList) > 0)
     {
      string parts[];
      int n = StringSplit(InpSymbolsList, ',', parts);
      int count = 0;
      ArrayResize(g_symbols, MathMin(n, InpMaxSymbols));
      for(int i = 0; i < n && count < InpMaxSymbols; i++)
        {
         string s = parts[i];
         StringTrimLeft(s);
         StringTrimRight(s);
         if(StringLen(s) < 3) continue;
         if(!SymbolSelect(s, true))
           {
            // try common suffixes
            if(!SymbolSelect(s + ".r", true) && !SymbolSelect(s + "m", true))
              {
               Print("AEGIS OHLC: cannot select ", s);
               continue;
              }
            if(SymbolSelect(s + ".r", true)) s = s + ".r";
            else if(SymbolSelect(s + "m", true)) s = s + "m";
           }
         g_symbols[count++] = s;
        }
      ArrayResize(g_symbols, count);
     }
   else
     {
      // Market Watch symbols (capped)
      int total = SymbolsTotal(true);
      int count = 0;
      ArrayResize(g_symbols, MathMin(total, InpMaxSymbols));
      for(int i = 0; i < total && count < InpMaxSymbols; i++)
        {
         string s = SymbolName(i, true);
         if(StringLen(s) < 3) continue;
         g_symbols[count++] = s;
        }
      ArrayResize(g_symbols, count);
     }
   ArrayResize(g_last_bar_time, ArraySize(g_symbols));
   ArrayInitialize(g_last_bar_time, 0);
   Print("AEGIS OHLC v2.00 symbols=", ArraySize(g_symbols), " mode=", EnumToString(InpMode));
  }

//+------------------------------------------------------------------+
bool PostOhlcForSymbol(const string symbol)
  {
   if(StringLen(InpApiKey) < 8)
     {
      Print("AEGIS OHLC: set InpApiKey");
      return false;
     }
   if(!SymbolSelect(symbol, true))
     {
      Print("AEGIS OHLC: SymbolSelect failed ", symbol);
      return false;
     }

   ENUM_TIMEFRAMES tf = ActiveTF();
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int n = CopyRates(symbol, tf, 0, InpBars, rates);
   if(n < 5)
     {
      Print("AEGIS OHLC: CopyRates failed ", symbol, " n=", n);
      return false;
     }

   string bars = "[";
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
      "{\"account_id\":\"%s\",\"symbol\":\"%s\",\"timeframe\":\"%s\",\"source\":\"mt5_ea_v2\",\"bars\":%s,\"current_bar\":%s,\"closed_bar\":%s}",
      JsonEscape(InpAccountId),
      JsonEscape(symbol),
      TfString(tf),
      bars, cur, closed
   );

   string url = BaseUrl() + "/api/mt5/ohlc/stream";
   char post[];
   char result[];
   string headers = "Content-Type: application/json\r\nX-API-Key: " + InpApiKey + "\r\n";
   StringToCharArray(body, post, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post, ArraySize(post) - 1);
   string result_headers;
   ResetLastError();
   int code = WebRequest("POST", url, headers, 15000, post, result, result_headers);
   if(code == -1)
     {
      Print("AEGIS OHLC: WebRequest failed for ", symbol, " err=", GetLastError());
      return false;
     }
   if(code < 200 || code >= 300)
     {
      Print("AEGIS OHLC: HTTP ", code, " ", symbol);
      return false;
     }
   return true;
  }

void PostAll()
  {
   int ok = 0, fail = 0;
   int n = ArraySize(g_symbols);
   if(n == 0) BuildSymbolList();
   n = ArraySize(g_symbols);
   for(int i = 0; i < n; i++)
     {
      if(PostOhlcForSymbol(g_symbols[i])) ok++;
      else fail++;
     }
   Print("AEGIS OHLC v2 cycle ok=", ok, " fail=", fail);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   BuildSymbolList();
   EventSetTimer(MathMax(5, InpTimerSec));
   PostAll();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer() { PostAll(); }

void OnTick()
  {
   // ChartOnly: fire on new bar for chart symbol
   if(InpMode != FEED_MODE_CHART_ONLY) return;
   if(ArraySize(g_symbols) < 1) return;
   datetime t = iTime(_Symbol, ActiveTF(), 0);
   if(ArraySize(g_last_bar_time) < 1) ArrayResize(g_last_bar_time, 1);
   if(t != g_last_bar_time[0])
     {
      g_last_bar_time[0] = t;
      PostOhlcForSymbol(_Symbol);
     }
  }
