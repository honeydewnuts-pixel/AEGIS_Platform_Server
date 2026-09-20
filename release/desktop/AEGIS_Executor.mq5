//+------------------------------------------------------------------+
//| AEGIS_Executor.mq5  v2.10                                        |
//| Multi-pair capable: same AccountId/ApiKey, independent symbols.  |
//| Mode ChartOnly = poll _Symbol only (Option A).                   |
//| Mode MultiPair = poll SymbolsList or /api/executor/universe.     |
//| Adaptive fill: IOC → FOK → RETURN.                               |
//|                                                                  |
//| Tools → Options → Expert Advisors → Allow WebRequest for API URL |
//+------------------------------------------------------------------+
#property copyright "LeverageFx / Honeydewnuts"
#property version   "2.10"
#property strict
#property description "AEGIS multi-pair executor: server signals → OrderSend per symbol"

enum ENUM_AEGIS_MODE
  {
   AEGIS_MODE_CHART_ONLY = 0,  // Single chart symbol (Option A)
   AEGIS_MODE_MULTI_PAIR = 1   // Many symbols, one EA (Option B)
  };

input string ServerUrl        = "https://aegis-api-0z1p.onrender.com";
input string AccountId        = "";
input string ApiKey           = "";
input ENUM_AEGIS_MODE ExecMode = AEGIS_MODE_CHART_ONLY;
input string SymbolsList      = "";  // MultiPair: "GBPUSD,EURUSD,USDJPY" empty=universe API
input double Lots             = 0.01;
input int    Slippage         = 30;
input int    MagicNumber      = 20260827;
input int    MaxSpreadPts     = 40;
input int    PollSeconds      = 5;
input int    MaxSignalAgeSec  = 300;
input bool   UseServerSignals = true;
input bool   UseLocalFileFallback = true;
input string SignalFile       = "aegis_signal.txt";
input bool   OnePositionPerSymbol = true;  // NOT account-wide
input int    WebTimeoutMs     = 8000;
input int    MaxSymbolsPerPoll = 24;

string   g_lastIds[];       // parallel to symbol base
string   g_lastIdSyms[];
string   lastLocalSig = "";

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

string BaseUrl()
  {
   string url = ServerUrl;
   if(StringLen(url) > 0 && StringGetCharacter(url, StringLen(url) - 1) == '/')
      url = StringSubstr(url, 0, StringLen(url) - 1);
   return url;
  }

//+------------------------------------------------------------------+
bool HasOpenPositionOn(const string symbol)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol) continue;
      return true;
     }
   return false;
  }

bool SpreadOk(const string symbol)
  {
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double pt  = SymbolInfoDouble(symbol, SYMBOL_POINT);
   if(pt <= 0) return false;
   int spread = (int)MathRound((ask - bid) / pt);
   return spread <= MaxSpreadPts;
  }

double NormalizeVolume(const string symbol, double vol)
  {
   double minLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(vol <= 0) vol = Lots;
   if(step <= 0) step = 0.01;
   vol = MathFloor(vol / step) * step;
   if(vol < minLot) vol = minLot;
   if(vol > maxLot) vol = maxLot;
   return NormalizeDouble(vol, 2);
  }

//+------------------------------------------------------------------+
ENUM_ORDER_TYPE_FILLING ResolveFilling(const string symbol)
  {
   // Prefer IOC, then FOK, then RETURN — broker-dependent
   int filling = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      return ORDER_FILLING_IOC;
   if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      return ORDER_FILLING_FOK;
   return ORDER_FILLING_RETURN;
  }

//+------------------------------------------------------------------+
string JsonGetString(const string json, const string key)
  {
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

double JsonGetNumber(const string json, const string key)
  {
   string pattern = "\"" + key + "\"";
   int p = StringFind(json, pattern);
   if(p < 0) return 0;
   int colon = StringFind(json, ":", p);
   if(colon < 0) return 0;
   string tail = StringSubstr(json, colon + 1);
   while(StringLen(tail) > 0 && (StringGetCharacter(tail, 0) == ' ' || StringGetCharacter(tail, 0) == '\t'))
      tail = StringSubstr(tail, 1);
   if(StringFind(tail, "null") == 0) return 0;
   if(StringGetCharacter(tail, 0) == '"')
      return StringToDouble(JsonGetString(json, key));
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
      Print("AEGIS WebRequest GET failed err=", GetLastError(),
            " — add ServerUrl to Allow WebRequest list");
      return "";
     }
   string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(code != 200)
     {
      Print("AEGIS HTTP ", code, " ", StringSubstr(body, 0, 180));
      return "";
     }
   return body;
  }

void AckServer(const string signalId, int ticket, bool ok, const string message, const string symbol)
  {
   if(StringLen(signalId) < 4) return;
   string url = BaseUrl() + "/api/executor/ack";
   string payload = "{";
   payload += "\"account_id\":\"" + AccountId + "\",";
   payload += "\"signal_id\":\"" + signalId + "\",";
   payload += "\"ticket\":" + IntegerToString(ticket) + ",";
   payload += "\"ok\":" + (ok ? "true" : "false") + ",";
   payload += "\"message\":\"" + message + "\",";
   payload += "\"symbol\":\"" + symbol + "\"";
   payload += "}";
   char data[];
   char result[];
   string result_headers;
   StringToCharArray(payload, data, 0, WHOLE_ARRAY, CP_UTF8);
   int n = ArraySize(data);
   if(n > 0 && data[n - 1] == 0) ArrayResize(data, n - 1);
   string headers = "X-API-Key: " + ApiKey + "\r\nContent-Type: application/json\r\n";
   WebRequest("POST", url, headers, WebTimeoutMs, data, result, result_headers);
  }

//+------------------------------------------------------------------+
bool WasHandled(const string signalId)
  {
   for(int i = 0; i < ArraySize(g_lastIds); i++)
      if(g_lastIds[i] == signalId) return true;
   return false;
  }

void MarkHandled(const string signalId, const string sym)
  {
   int n = ArraySize(g_lastIds);
   ArrayResize(g_lastIds, n + 1);
   ArrayResize(g_lastIdSyms, n + 1);
   g_lastIds[n] = signalId;
   g_lastIdSyms[n] = sym;
   // cap memory
   if(ArraySize(g_lastIds) > 64)
     {
      for(int i = 0; i < 32; i++)
        {
         g_lastIds[i] = g_lastIds[i + 32];
         g_lastIdSyms[i] = g_lastIdSyms[i + 32];
        }
      ArrayResize(g_lastIds, 32);
      ArrayResize(g_lastIdSyms, 32);
     }
  }

//+------------------------------------------------------------------+
bool ExecuteTradeOn(const string symbol, const string side, double volume, double sl, double tp, const string signalId)
  {
   if(!SymbolSelect(symbol, true))
     {
      Print("AEGIS: SymbolSelect failed ", symbol);
      AckServer(signalId, 0, false, "symbol_select", symbol);
      return false;
     }
   if(OnePositionPerSymbol && HasOpenPositionOn(symbol))
     {
      Print("AEGIS: already open ", symbol);
      AckServer(signalId, 0, false, "already_open", symbol);
      return false;
     }
   if(!SpreadOk(symbol))
     {
      Print("AEGIS: spread wide ", symbol);
      AckServer(signalId, 0, false, "spread", symbol);
      return false;
     }

   double vol = NormalizeVolume(symbol, volume);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   ENUM_ORDER_TYPE_FILLING fill = ResolveFilling(symbol);

   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = symbol;
   req.volume       = vol;
   req.deviation    = Slippage;
   req.magic        = MagicNumber;
   req.comment      = "AEGIS " + signalId;
   req.type_filling = fill;

   if(side == "BUY")
     {
      req.type  = ORDER_TYPE_BUY;
      req.price = SymbolInfoDouble(symbol, SYMBOL_ASK);
      if(sl > 0) req.sl = NormalizeDouble(sl, digits);
      if(tp > 0) req.tp = NormalizeDouble(tp, digits);
     }
   else if(side == "SELL")
     {
      req.type  = ORDER_TYPE_SELL;
      req.price = SymbolInfoDouble(symbol, SYMBOL_BID);
      if(sl > 0) req.sl = NormalizeDouble(sl, digits);
      if(tp > 0) req.tp = NormalizeDouble(tp, digits);
     }
   else return false;

   ResetLastError();
   bool ok = OrderSend(req, res);
   // Retry once with alternate filling if broker rejects fill mode
   if((!ok || (res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_DONE_PARTIAL))
      && (res.retcode == TRADE_RETCODE_INVALID_FILL || res.retcode == 10030))
     {
      Print("AEGIS: fill mode rejected, retry RETURN on ", symbol);
      req.type_filling = ORDER_FILLING_RETURN;
      ZeroMemory(res);
      ok = OrderSend(req, res);
     }

   if(!ok || (res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_DONE_PARTIAL))
     {
      Print("AEGIS OrderSend fail ", symbol, " err=", GetLastError(), " ret=", res.retcode);
      AckServer(signalId, (int)res.order, false, IntegerToString(res.retcode), symbol);
      return false;
     }
   Print("AEGIS OK ", side, " ", symbol, " vol=", vol, " ticket=", res.order, " id=", signalId);
   AckServer(signalId, (int)res.order, true, "ok", symbol);
   return true;
  }

//+------------------------------------------------------------------+
bool HandleSignalJsonObject(const string obj)
  {
   string side = JsonGetString(obj, "side");
   if(side == "") side = JsonGetString(obj, "signal");
   StringToUpper(side);
   if(side != "BUY" && side != "SELL") return false;

   string signalId = JsonGetString(obj, "signal_id");
   if(signalId != "" && WasHandled(signalId)) return false;

   string sym = JsonGetString(obj, "symbol");
   if(sym == "") sym = _Symbol;
   sym = NormalizeSymbolBase(sym);
   // Prefer broker suffix matching chart if needed
   string tradeSym = sym;
   if(!SymbolInfoInteger(tradeSym, SYMBOL_SELECT))
     {
      // try chart symbol if base matches
      if(NormalizeSymbolBase(_Symbol) == sym)
         tradeSym = _Symbol;
     }

   long created = (long)JsonGetNumber(obj, "created_at_ms");
   if(created > 0)
     {
      long ageSec = ((long)TimeGMT() * 1000 - created) / 1000;
      if(ageSec > MaxSignalAgeSec)
        {
         MarkHandled(signalId, sym);
         AckServer(signalId, 0, false, "stale", tradeSym);
         return false;
        }
     }

   double vol = JsonGetNumber(obj, "volume");
   double sl  = JsonGetNumber(obj, "stop_loss");
   double tp  = JsonGetNumber(obj, "take_profit");
   MarkHandled(signalId, sym);
   return ExecuteTradeOn(tradeSym, side, vol, sl, tp, signalId);
  }

// Extract successive {...} objects from a JSON array value of "signals"
void ProcessSignalsArray(const string body)
  {
   int key = StringFind(body, "\"signals\"");
   if(key < 0) return;
   int arr = StringFind(body, "[", key);
   if(arr < 0) return;
   int depth = 0;
   int start = -1;
   for(int i = arr; i < StringLen(body); i++)
     {
      ushort c = StringGetCharacter(body, i);
      if(c == '{')
        {
         if(depth == 0) start = i;
         depth++;
        }
      else if(c == '}')
        {
         depth--;
         if(depth == 0 && start >= 0)
           {
            string obj = StringSubstr(body, start, i - start + 1);
            HandleSignalJsonObject(obj);
            start = -1;
           }
        }
      else if(c == ']' && depth == 0)
         break;
     }
  }

//+------------------------------------------------------------------+
void PollChartOnly()
  {
   string base = NormalizeSymbolBase(_Symbol);
   string url = BaseUrl() + "/api/executor/pending?account_id=" + AccountId + "&symbol=" + base;
   string body = HttpGet(url);
   if(body == "") return;
   if(!JsonGetBool(body, "has_signal")) return;
   HandleSignalJsonObject(body);
  }

void PollMultiPair()
  {
   string url = BaseUrl() + "/api/executor/pending-batch?account_id=" + AccountId;
   if(StringLen(SymbolsList) > 0)
      url += "&symbols=" + SymbolsList;
   // else empty symbols → server uses Good universe
   string body = HttpGet(url);
   if(body == "") return;
   ProcessSignalsArray(body);
  }

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

void PollLocalFallback()
  {
   if(!UseLocalFileFallback) return;
   string sig = ReadLocalSignal();
   if(sig == "" || sig == lastLocalSig) return;
   if(sig != "BUY" && sig != "SELL") return;
   lastLocalSig = sig;
   ExecuteTradeOn(_Symbol, sig, Lots, 0, 0, "local");
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   Print("AEGIS_Executor v2.10 mode=", EnumToString(ExecMode),
         " chart=", _Symbol, " account=", AccountId);
   if(StringLen(AccountId) < 3 || StringLen(ApiKey) < 4)
      Print("AEGIS WARNING: set AccountId and ApiKey");
   EventSetTimer(MathMax(2, PollSeconds));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   if(UseServerSignals)
     {
      if(ExecMode == AEGIS_MODE_MULTI_PAIR)
         PollMultiPair();
      else
         PollChartOnly();
     }
   if(UseLocalFileFallback)
      PollLocalFallback();
  }
