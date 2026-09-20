//+------------------------------------------------------------------+
//| AEGIS_Executor.mq5  v2.11                                        |
//| Multi-pair + robust broker-symbol resolve + safe handled state.  |
//| MarkHandled only after successful OrderSend (or permanent fail). |
//| Adaptive fill from SYMBOL_FILLING_MODE; rich ACK payload.        |
//+------------------------------------------------------------------+
#property copyright "LeverageFx / Honeydewnuts"
#property version   "2.11"
#property strict
#property description "AEGIS multi-pair executor v2.11 hardened"

enum ENUM_AEGIS_MODE
  {
   AEGIS_MODE_CHART_ONLY = 0,
   AEGIS_MODE_MULTI_PAIR = 1
  };

input string ServerUrl        = "https://aegis-api-0z1p.onrender.com";
input string AccountId        = "";
input string ApiKey           = "";
input ENUM_AEGIS_MODE ExecMode = AEGIS_MODE_CHART_ONLY;
input string SymbolsList      = "";
input double Lots             = 0.01;
input int    Slippage         = 30;
input int    MagicNumber      = 20260827;
input int    MaxSpreadPts     = 40;
input int    PollSeconds      = 5;
input int    MaxSignalAgeSec  = 300;
input bool   UseServerSignals = true;
input bool   UseLocalFileFallback = false;
input string SignalFile       = "aegis_signal.txt";
input bool   OnePositionPerSymbol = true;
input int    WebTimeoutMs     = 8000;
input int    MaxSymbolsPerPoll = 24;
input int    MaxRetriesTransient = 3;  // spread/requote style failures

string g_handledIds[];
string g_retryIds[];
int    g_retryCount[];
string lastLocalSig = "";

//+------------------------------------------------------------------+
string NormalizeSymbolBase(string sym)
  {
   string s = sym;
   StringToUpper(s);
   int hash = StringFind(s, "#");
   if(hash > 0) s = StringSubstr(s, 0, hash);
   int d = StringFind(s, ".");
   if(d > 0) s = StringSubstr(s, 0, d);
   if(StringLen(s) == 7)
     {
      ushort last = StringGetCharacter(s, 6);
      if(last == 'M' || last == 'I' || last == 'P' || last == 'C')
         s = StringSubstr(s, 0, 6);
     }
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
// Canonical AEGIS base → actual broker symbol in Market Watch / terminal
string ResolveBrokerSymbol(const string canonical)
  {
   string base = NormalizeSymbolBase(canonical);
   if(StringLen(base) < 3) return "";

   // 1) exact
   if(SymbolSelect(base, true) && SymbolInfoInteger(base, SYMBOL_EXIST))
      return base;

   // 2) common suffixes
   string candidates[];
   ArrayResize(candidates, 12);
   candidates[0] = base + ".r";
   candidates[1] = base + "m";
   candidates[2] = base + ".i";
   candidates[3] = base + "#";
   candidates[4] = base + ".pro";
   candidates[5] = base + ".raw";
   candidates[6] = base + ".ecn";
   candidates[7] = base + ".std";
   candidates[8] = base + ".a";
   candidates[9] = base + ".b";
   candidates[10] = base + ".c";
   candidates[11] = base + "i";
   for(int i = 0; i < ArraySize(candidates); i++)
     {
      if(SymbolSelect(candidates[i], true) && SymbolInfoInteger(candidates[i], SYMBOL_EXIST))
         return candidates[i];
     }

   // 3) scan Market Watch
   int total = SymbolsTotal(true);
   for(int i = 0; i < total; i++)
     {
      string name = SymbolName(i, true);
      if(NormalizeSymbolBase(name) == base)
        {
         if(SymbolSelect(name, true))
            return name;
        }
     }

   // 4) full symbols (not only selected)
   total = SymbolsTotal(false);
   for(int i = 0; i < total; i++)
     {
      string name = SymbolName(i, false);
      if(NormalizeSymbolBase(name) == base)
        {
         if(SymbolSelect(name, true))
            return name;
        }
     }

   // 5) chart fallback if same base
   if(NormalizeSymbolBase(_Symbol) == base)
      return _Symbol;

   Print("AEGIS: ResolveBrokerSymbol failed for ", base);
   return "";
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

// Build ordered list of supported fill modes for this symbol
void GetSupportedFillModes(const string symbol, ENUM_ORDER_TYPE_FILLING &modes[])
  {
   int filling = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   int n = 0;
   ArrayResize(modes, 3);
   if((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC)
      modes[n++] = ORDER_FILLING_IOC;
   if((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK)
      modes[n++] = ORDER_FILLING_FOK;
   if((filling & SYMBOL_FILLING_RETURN) == SYMBOL_FILLING_RETURN)
      modes[n++] = ORDER_FILLING_RETURN;
   // if broker reports nothing, try IOC then FOK then RETURN
   if(n == 0)
     {
      modes[0] = ORDER_FILLING_IOC;
      modes[1] = ORDER_FILLING_FOK;
      modes[2] = ORDER_FILLING_RETURN;
      n = 3;
     }
   ArrayResize(modes, n);
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
      else if(StringLen(num) > 0) break;
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
      Print("AEGIS WebRequest GET failed err=", GetLastError());
      return "";
     }
   string body = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
   if(code != 200)
     {
      Print("AEGIS HTTP ", code, " ", StringSubstr(body, 0, 160));
      return "";
     }
   return body;
  }

void AckServerFull(const string signalId, const string symbol, const string side,
                   double volume, ulong orderTicket, ulong dealTicket, ulong positionTicket,
                   int retcode, bool ok, const string message)
  {
   if(StringLen(signalId) < 4) return;
   string url = BaseUrl() + "/api/executor/ack";
   string payload = "{";
   payload += "\"account_id\":\"" + AccountId + "\",";
   payload += "\"signal_id\":\"" + signalId + "\",";
   payload += "\"ticket\":" + IntegerToString((int)orderTicket) + ",";
   payload += "\"order_ticket\":" + IntegerToString((int)orderTicket) + ",";
   payload += "\"deal_ticket\":" + IntegerToString((int)dealTicket) + ",";
   payload += "\"position_ticket\":" + IntegerToString((int)positionTicket) + ",";
   payload += "\"retcode\":" + IntegerToString(retcode) + ",";
   payload += "\"ok\":" + (ok ? "true" : "false") + ",";
   payload += "\"message\":\"" + message + "\",";
   payload += "\"symbol\":\"" + symbol + "\",";
   payload += "\"side\":\"" + side + "\",";
   payload += "\"volume\":" + DoubleToString(volume, 2);
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
   for(int i = 0; i < ArraySize(g_handledIds); i++)
      if(g_handledIds[i] == signalId) return true;
   return false;
  }

void MarkHandled(const string signalId)
  {
   if(signalId == "" || WasHandled(signalId)) return;
   int n = ArraySize(g_handledIds);
   ArrayResize(g_handledIds, n + 1);
   g_handledIds[n] = signalId;
   if(ArraySize(g_handledIds) > 80)
     {
      for(int i = 0; i < 40; i++) g_handledIds[i] = g_handledIds[i + 40];
      ArrayResize(g_handledIds, 40);
     }
   // clear retry tracking
   for(int i = 0; i < ArraySize(g_retryIds); i++)
     {
      if(g_retryIds[i] == signalId)
        {
         g_retryIds[i] = "";
         g_retryCount[i] = 0;
        }
     }
  }

int GetRetryCount(const string signalId)
  {
   for(int i = 0; i < ArraySize(g_retryIds); i++)
      if(g_retryIds[i] == signalId) return g_retryCount[i];
   return 0;
  }

void IncRetry(const string signalId)
  {
   for(int i = 0; i < ArraySize(g_retryIds); i++)
     {
      if(g_retryIds[i] == signalId)
        {
         g_retryCount[i]++;
         return;
        }
     }
   int n = ArraySize(g_retryIds);
   ArrayResize(g_retryIds, n + 1);
   ArrayResize(g_retryCount, n + 1);
   g_retryIds[n] = signalId;
   g_retryCount[n] = 1;
  }

bool IsTransientRetcode(int retcode)
  {
   // requote, price off, busy, too many requests, connection, timeout-ish
   if(retcode == TRADE_RETCODE_REQUOTE) return true;
   if(retcode == TRADE_RETCODE_PRICE_OFF) return true;
   if(retcode == TRADE_RETCODE_PRICE_CHANGED) return true;
   if(retcode == TRADE_RETCODE_CONNECTION) return true;
   if(retcode == TRADE_RETCODE_TIMEOUT) return true;
   if(retcode == TRADE_RETCODE_TOO_MANY_REQUESTS) return true;
   if(retcode == TRADE_RETCODE_LOCKED) return true;
   return false;
  }

//+------------------------------------------------------------------+
// Returns: 1 success, 0 transient fail (retry), -1 permanent fail
int ExecuteTradeOn(const string brokerSymbol, const string side, double volume,
                   double sl, double tp, const string signalId, const string canonical)
  {
   if(StringLen(brokerSymbol) < 1)
     {
      AckServerFull(signalId, canonical, side, 0, 0, 0, 0, -1, false, "resolve_failed");
      return -1;
     }
   if(OnePositionPerSymbol && HasOpenPositionOn(brokerSymbol))
     {
      AckServerFull(signalId, brokerSymbol, side, 0, 0, 0, 0, -2, false, "already_open");
      return -1; // permanent for this signal
     }
   if(!SpreadOk(brokerSymbol))
     {
      Print("AEGIS: spread wide ", brokerSymbol, " — will retry");
      return 0; // transient
     }

   double vol = NormalizeVolume(brokerSymbol, volume);
   int digits = (int)SymbolInfoInteger(brokerSymbol, SYMBOL_DIGITS);
   ENUM_ORDER_TYPE_FILLING modes[];
   GetSupportedFillModes(brokerSymbol, modes);

   MqlTradeRequest req;
   MqlTradeResult  res;
   int lastRet = 0;

   for(int m = 0; m < ArraySize(modes); m++)
     {
      ZeroMemory(req);
      ZeroMemory(res);
      req.action       = TRADE_ACTION_DEAL;
      req.symbol       = brokerSymbol;
      req.volume       = vol;
      req.deviation    = Slippage;
      req.magic        = MagicNumber;
      req.comment      = "AEGIS " + signalId;
      req.type_filling = modes[m];

      if(side == "BUY")
        {
         req.type  = ORDER_TYPE_BUY;
         req.price = SymbolInfoDouble(brokerSymbol, SYMBOL_ASK);
         if(sl > 0) req.sl = NormalizeDouble(sl, digits);
         if(tp > 0) req.tp = NormalizeDouble(tp, digits);
        }
      else if(side == "SELL")
        {
         req.type  = ORDER_TYPE_SELL;
         req.price = SymbolInfoDouble(brokerSymbol, SYMBOL_BID);
         if(sl > 0) req.sl = NormalizeDouble(sl, digits);
         if(tp > 0) req.tp = NormalizeDouble(tp, digits);
        }
      else return -1;

      ResetLastError();
      bool sent = OrderSend(req, res);
      lastRet = (int)res.retcode;
      if(sent && (res.retcode == TRADE_RETCODE_DONE || res.retcode == TRADE_RETCODE_DONE_PARTIAL))
        {
         Print("AEGIS OK ", side, " ", brokerSymbol, " vol=", vol,
               " order=", res.order, " deal=", res.deal, " id=", signalId);
         AckServerFull(signalId, brokerSymbol, side, vol, res.order, res.deal, res.order,
                       (int)res.retcode, true, "ok");
         return 1;
        }
      if(res.retcode == TRADE_RETCODE_INVALID_FILL)
         continue; // try next fill mode
      if(IsTransientRetcode((int)res.retcode))
        {
         Print("AEGIS transient ret=", res.retcode, " ", brokerSymbol);
         return 0;
        }
      // other failure — try next fill mode anyway
     }

   Print("AEGIS OrderSend fail ", brokerSymbol, " ret=", lastRet);
   AckServerFull(signalId, brokerSymbol, side, vol, 0, 0, 0, lastRet, false, IntegerToString(lastRet));
   return -1;
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

   string canonical = JsonGetString(obj, "symbol");
   if(canonical == "") canonical = _Symbol;
   canonical = NormalizeSymbolBase(canonical);

   long created = (long)JsonGetNumber(obj, "created_at_ms");
   if(created > 0)
     {
      long ageSec = ((long)TimeGMT() * 1000 - created) / 1000;
      if(ageSec > MaxSignalAgeSec)
        {
         MarkHandled(signalId);
         AckServerFull(signalId, canonical, side, 0, 0, 0, 0, -3, false, "stale");
         return false;
        }
     }

   double vol = JsonGetNumber(obj, "volume");
   double sl  = JsonGetNumber(obj, "stop_loss");
   double tp  = JsonGetNumber(obj, "take_profit");

   string brokerSym = ResolveBrokerSymbol(canonical);
   int rc = ExecuteTradeOn(brokerSym, side, vol, sl, tp, signalId, canonical);

   if(rc == 1)
     {
      MarkHandled(signalId);
      return true;
     }
   if(rc == -1)
     {
      MarkHandled(signalId); // permanent fail
      return false;
     }
   // transient: retry later, do NOT mark handled
   IncRetry(signalId);
   if(GetRetryCount(signalId) >= MaxRetriesTransient)
     {
      MarkHandled(signalId);
      AckServerFull(signalId, brokerSym, side, 0, 0, 0, 0, -4, false, "max_retries");
     }
   return false;
  }

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
            HandleSignalJsonObject(StringSubstr(body, start, i - start + 1));
            start = -1;
           }
        }
      else if(c == ']' && depth == 0)
         break;
     }
  }

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
   string list = SymbolsList;
   if(StringLen(list) > 0 && MaxSymbolsPerPoll > 0)
     {
      string parts[];
      int n = StringSplit(list, ',', parts);
      string capped = "";
      int take = MathMin(n, MaxSymbolsPerPoll);
      for(int i = 0; i < take; i++)
        {
         string s = parts[i];
         StringTrimLeft(s); StringTrimRight(s);
         if(StringLen(s) < 3) continue;
         if(StringLen(capped) > 0) capped += ",";
         capped += NormalizeSymbolBase(s);
        }
      list = capped;
     }
   if(StringLen(list) > 0)
      url += "&symbols=" + list;
   url += "&max_symbols=" + IntegerToString(MaxSymbolsPerPoll);
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
   StringTrimLeft(s); StringTrimRight(s); StringToUpper(s);
   return s;
  }

void PollLocalFallback()
  {
   if(!UseLocalFileFallback) return;
   string sig = ReadLocalSignal();
   if(sig == "" || sig == lastLocalSig) return;
   if(sig != "BUY" && sig != "SELL") return;
   lastLocalSig = sig;
   string broker = ResolveBrokerSymbol(NormalizeSymbolBase(_Symbol));
   if(ExecuteTradeOn(broker, sig, Lots, 0, 0, "local", NormalizeSymbolBase(_Symbol)) == 1)
      lastLocalSig = sig;
  }

int OnInit()
  {
   Print("AEGIS_Executor v2.11 mode=", EnumToString(ExecMode),
         " chart=", _Symbol, " account=", AccountId);
   EventSetTimer(MathMax(2, PollSeconds));
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
  {
   if(UseServerSignals)
     {
      if(ExecMode == AEGIS_MODE_MULTI_PAIR) PollMultiPair();
      else PollChartOnly();
     }
   if(UseLocalFileFallback) PollLocalFallback();
  }
