//+------------------------------------------------------------------+
//| AEGIS_Executor.mq5                                               |
//| Polls AEGIS server for BUY/SELL and executes on this chart.      |
//| Fallback: local Common/Files/aegis_signal.txt                    |
//|                                                                  |
//| REQUIRED in MT5:                                                 |
//|  Tools → Options → Expert Advisors →                             |
//|  ☑ Allow WebRequest for listed URL                               |
//|  Add: https://aegis-api-0z1p.onrender.com                        |
//|  ☑ Allow Algo Trading                                            |
//+------------------------------------------------------------------+
#property copyright "LeverageFx / Honeydewnuts"
#property version   "2.00"
#property strict
#property description "AEGIS Executor: server signal → OrderSend on attached symbol"

input string ServerUrl     = "https://aegis-api-0z1p.onrender.com";
input string AccountId     = "";
input string ApiKey        = "";
input double Lots          = 0.01;      // Used if server does not send volume
input int    Slippage      = 30;
input int    MagicNumber   = 20260827;
input int    MaxSpreadPts  = 40;
input int    PollSeconds   = 5;
input int    MaxSignalAgeSec = 300;     // ignore stale server signals
input bool   UseServerSignals = true;   // primary path
input bool   UseLocalFileFallback = true;
input string SignalFile    = "aegis_signal.txt";
input bool   OnePositionOnly = true;
input int    WebTimeoutMs  = 8000;

string   lastSignalId = "";
string   lastLocalSig = "";
datetime lastPollTime = 0;

//+------------------------------------------------------------------+
string NormalizeSymbolBase(string sym)
  {
   string s = sym;
   int dot = StringFind(s, ".");
   if(dot > 0) s = StringSubstr(s, 0, dot);
   int hash = StringFind(s, "#");
   if(hash > 0) s = StringSubstr(s, 0, hash);
   StringToUpper(s);
   return s;
  }

//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
bool SpreadOk()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(pt <= 0) return false;
   int spread = (int)MathRound((ask - bid) / pt);
   return spread <= MaxSpreadPts;
  }

//+------------------------------------------------------------------+
double NormalizeVolume(double vol)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vol <= 0) vol = Lots;
   if(step <= 0) step = 0.01;
   vol = MathFloor(vol / step) * step;
   if(vol < minLot) vol = minLot;
   if(vol > maxLot) vol = maxLot;
   return NormalizeDouble(vol, 2);
  }

//+------------------------------------------------------------------+
bool ExecuteTrade(const string side, double volume, double sl, double tp, const string signalId)
  {
   if(OnePositionOnly && HasOpenPosition())
     {
      Print("AEGIS: position already open on ", _Symbol);
      return false;
     }
   if(!SpreadOk())
     {
      Print("AEGIS: spread too wide");
      return false;
     }

   double vol = NormalizeVolume(volume);
   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = vol;
   req.deviation    = Slippage;
   req.magic        = MagicNumber;
   req.comment      = "AEGIS " + signalId;
   req.type_filling = ORDER_FILLING_IOC;

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   if(side == "BUY")
     {
      req.type  = ORDER_TYPE_BUY;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(sl > 0) req.sl = NormalizeDouble(sl, digits);
      if(tp > 0) req.tp = NormalizeDouble(tp, digits);
     }
   else if(side == "SELL")
     {
      req.type  = ORDER_TYPE_SELL;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(sl > 0) req.sl = NormalizeDouble(sl, digits);
      if(tp > 0) req.tp = NormalizeDouble(tp, digits);
     }
   else return false;

   ResetLastError();
   bool ok = OrderSend(req, res);
   if(!ok || res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_DONE_PARTIAL)
     {
      Print("AEGIS OrderSend failed err=", GetLastError(), " retcode=", res.retcode, " comment=", res.comment);
      AckServer(signalId, (int)res.order, false, IntegerToString(res.retcode));
      return false;
     }
   Print("AEGIS trade OK ", side, " vol=", vol, " ticket=", res.order, " deal=", res.deal, " signal=", signalId);
   AckServer(signalId, (int)res.order, true, "ok");
   return true;
  }

//+------------------------------------------------------------------+
string JsonGetString(const string json, const string key)
  {
   // naive "key":"value" extractor
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return "";
   int colon = StringFind(json, ":", p);
   if(colon < 0) return "";
   int q1 = StringFind(json, "\"", colon);
   if(q1 < 0) return "";
   int q2 = StringFind(json, "\"", q1 + 1);
   if(q2 < 0) return "";
   return StringSubstr(json, q1 + 1, q2 - q1 - 1);
  }

//+------------------------------------------------------------------+
double JsonGetNumber(const string json, const string key)
  {
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return 0;
   int colon = StringFind(json, ":", p);
   if(colon < 0) return 0;
   string tail = StringSubstr(json, colon + 1);
   // skip space
   while(StringLen(tail) > 0 && (StringGetCharacter(tail, 0) == ' ' || StringGetCharacter(tail, 0) == '\t'))
      tail = StringSubstr(tail, 1);
   // null?
   if(StringFind(tail, "null") == 0) return 0;
   // quoted number?
   if(StringGetCharacter(tail, 0) == '"')
     {
      string s = JsonGetString(json, key);
      return StringToDouble(s);
     }
   // read until non-numeric
   string num = "";
   for(int i = 0; i < StringLen(tail); i++)
     {
      ushort c = StringGetCharacter(tail, i);
      if((c >= '0' && c <= '9') || c == '.' || c == '-' || c == '+')
         num += CharToString((uchar)c);
      else if(StringLen(num) > 0)
         break;
     }
   return StringToDouble(num);
  }

//+------------------------------------------------------------------+
bool JsonGetBool(const string json, const string key)
  {
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return false;
   int colon = StringFind(json, ":", p);
   if(colon < 0) return false;
   string tail = StringSubstr(json, colon + 1, 20);
   StringToLower(tail);
   return (StringFind(tail, "true") >= 0);
  }

//+------------------------------------------------------------------+
string HttpGet(const string url)
  {
   char data[];
   char result[];
   string result_headers;
   string headers = "X-API-Key: " + ApiKey + "\r\nContent-Type: application/json\r\n";
   ArrayResize(data, 0);
   ResetLastError();
   int code = WebRequest("GET", url, headers, WebTimeoutMs, data, result, result_headers);
   if(code == -1)
     {
      int err = GetLastError();
      Print("AEGIS WebRequest GET failed err=", err,
            " — add ServerUrl to Tools→Options→Expert Advisors→Allow WebRequest");
      return "";
     }
   string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(code != 200)
     {
      Print("AEGIS pending HTTP ", code, " body=", StringSubstr(body, 0, 200));
      return "";
     }
   return body;
  }

//+------------------------------------------------------------------+
void AckServer(const string signalId, int ticket, bool ok, const string message)
  {
   if(StringLen(ServerUrl) < 8 || StringLen(ApiKey) < 4 || StringLen(signalId) < 4)
      return;
   string url = ServerUrl;
   // strip trailing slash
   if(StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   url += "/api/executor/ack";

   string payload = "{";
   payload += "\"account_id\":\"" + AccountId + "\",";
   payload += "\"signal_id\":\"" + signalId + "\",";
   payload += "\"ticket\":" + IntegerToString(ticket) + ",";
   payload += "\"ok\":" + (ok ? "true" : "false") + ",";
   payload += "\"message\":\"" + message + "\",";
   payload += "\"symbol\":\"" + _Symbol + "\"";
   payload += "}";

   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   // remove trailing null from StringToCharArray
   int n = ArraySize(data);
   if(n > 0 && data[n - 1] == 0) ArrayResize(data, n - 1);

   string headers = "X-API-Key: " + ApiKey + "\r\nContent-Type: application/json\r\n";
   ResetLastError();
   int code = WebRequest("POST", url, headers, WebTimeoutMs, data, result, result_headers);
   if(code == -1)
      Print("AEGIS ACK WebRequest failed err=", GetLastError());
   else
      Print("AEGIS ACK HTTP ", code, " signal=", signalId);
  }

//+------------------------------------------------------------------+
bool PollServerSignal()
  {
   if(!UseServerSignals) return false;
   if(StringLen(ServerUrl) < 8 || StringLen(AccountId) < 3 || StringLen(ApiKey) < 4)
     {
      Print("AEGIS: set ServerUrl, AccountId, ApiKey inputs");
      return false;
     }

   string base = NormalizeSymbolBase(_Symbol);
   string url = ServerUrl;
   if(StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   url += "/api/executor/pending?account_id=" + AccountId + "&symbol=" + base;

   string body = HttpGet(url);
   if(body == "") return false;

   bool has = JsonGetBool(body, "has_signal");
   if(!has) return false;

   string side = JsonGetString(body, "side");
   if(side == "") side = JsonGetString(body, "signal");
   StringToUpper(side);
   if(side != "BUY" && side != "SELL") return false;

   string signalId = JsonGetString(body, "signal_id");
   if(signalId != "" && signalId == lastSignalId)
      return false; // already handled

   // freshness
   long created = (long)JsonGetNumber(body, "created_at_ms");
   if(created > 0)
     {
      long nowMs = (long)TimeGMT() * 1000;
      // TimeGMT is seconds; approximate age
      long ageSec = (nowMs - created) / 1000;
      if(ageSec > MaxSignalAgeSec)
        {
         Print("AEGIS: signal too old ageSec=", ageSec);
         lastSignalId = signalId;
         AckServer(signalId, 0, false, "stale");
         return false;
        }
     }

   double vol = JsonGetNumber(body, "volume");
   double sl  = JsonGetNumber(body, "stop_loss");
   double tp  = JsonGetNumber(body, "take_profit");
   string rule = JsonGetString(body, "rule_name");
   Print("AEGIS server signal ", side, " rule=", rule, " id=", signalId);

   lastSignalId = signalId;
   return ExecuteTrade(side, vol, sl, tp, signalId);
  }

//+------------------------------------------------------------------+
string ReadLocalSignal()
  {
   int h = FileOpen(SignalFile, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return "";
   string s = FileReadString(h);
   FileClose(h);
   StringTrimLeft(s);
   StringTrimRight(s);
   StringToUpper(s);
   return s;
  }

//+------------------------------------------------------------------+
void PollLocalFallback()
  {
   if(!UseLocalFileFallback) return;
   string sig = ReadLocalSignal();
   if(sig == "" || sig == lastLocalSig) return;
   if(sig != "BUY" && sig != "SELL") return;
   lastLocalSig = sig;
   Print("AEGIS local file signal ", sig);
   ExecuteTrade(sig, Lots, 0, 0, "local");
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   Print("AEGIS_Executor v2.00 init symbol=", _Symbol,
         " server=", ServerUrl, " account=", AccountId,
         " UseServer=", UseServerSignals);
   if(StringLen(AccountId) < 3 || StringLen(ApiKey) < 4)
      Print("AEGIS WARNING: AccountId / ApiKey empty — server poll will fail");
   EventSetTimer(MathMax(2, PollSeconds));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   lastPollTime = TimeCurrent();
   if(UseServerSignals)
      PollServerSignal();
   else if(UseLocalFileFallback)
      PollLocalFallback();
   else
      PollLocalFallback();

   // If server returned nothing, optional local fallback same tick cycle
   if(UseServerSignals && UseLocalFileFallback)
      PollLocalFallback();
  }
