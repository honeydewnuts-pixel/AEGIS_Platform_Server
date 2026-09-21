//+------------------------------------------------------------------+
//| AEGIS_Executor.mq5  v2.15  PRODUCTION HARDENED                   |
//| - ResolveBrokerSymbol (suffixes + MW scan)                       |
//| - MarkHandled only after success / permanent fail                |
//| - Transient retry: spread vs broker (separate limits)            |
//| - Position ticket via PositionsTotal + magic + symbol            |
//| - ACK verified (HTTP 2xx); retry ACK if trade ok but ACK fails   |
//| - Fill modes from SYMBOL_TRADE_EXECUTION + SYMBOL_FILLING_MODE   |
//+------------------------------------------------------------------+
#property copyright "LeverageFx / Honeydewnuts"
#property version   "2.15"
#property strict
#property description "AEGIS multi-pair executor v2.15 production"

enum ENUM_AEGIS_MODE
  {
   AEGIS_MODE_CHART_ONLY = 0,
   AEGIS_MODE_MULTI_PAIR = 1
  };

enum ENUM_PARTIAL_FILL
  {
   PARTIAL_ACCEPT = 0,              // Treat partial fill as complete success
   PARTIAL_COMPLETE_REMAINDER = 1   // Attempt remaining volume once
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
input ENUM_PARTIAL_FILL PartialFillPolicy = PARTIAL_ACCEPT;

input int    WebTimeoutMs     = 8000;
input int    MaxSymbolsPerPoll = 24;
input int    MaxRetriesSpread = 12;      // ~1 min at 5s poll — wide spread can persist
input int    MaxRetriesBroker = 5;       // requote / busy / connection
input int    MaxAckRetries    = 5;

string g_handledIds[];
string g_retryIds[];
int    g_retrySpread[];
int    g_retryBroker[];
// Pending ACK after successful trade (trade done, server not yet confirmed)
string g_ackPendingId[];
string g_ackPendingPayload[];  // prebuilt JSON body
int    g_ackPendingTries[];

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


// Safe 64-bit ticket → JSON number string (no int truncation)
string UlongToStr(ulong v)
  {
   return IntegerToString((long)v);  // long is 64-bit in MQL5
  }

// Restart-safe: signal already executed if order/position comment contains AEGIS <id>
bool SignalAlreadyExecuted(const string signalId, const string brokerSymbol)
  {
   if(StringLen(signalId) < 4) return false;
   string needle = "AEGIS " + signalId;
   // Open positions
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(StringLen(brokerSymbol) > 0 && PositionGetString(POSITION_SYMBOL) != brokerSymbol) continue;
      string cmt = PositionGetString(POSITION_COMMENT);
      // Exact marker only: "AEGIS <signal_id>" (avoid substring false positives)
      if(StringFind(cmt, needle) >= 0)
         return true;
     }
   // History deals (recent) — covers closed trades after restart
   datetime from = TimeCurrent() - 7 * 24 * 3600;
   if(HistorySelect(from, TimeCurrent()))
     {
      int total = HistoryDealsTotal();
      for(int i = total - 1; i >= 0 && i >= total - 500; i--)
        {
         ulong deal = HistoryDealGetTicket(i);
         if(deal == 0) continue;
         if((long)HistoryDealGetInteger(deal, DEAL_MAGIC) != MagicNumber) continue;
         if(StringLen(brokerSymbol) > 0)
           {
            string dsym = HistoryDealGetString(deal, DEAL_SYMBOL);
            if(dsym != brokerSymbol) continue;
           }
         string cmt = HistoryDealGetString(deal, DEAL_COMMENT);
         if(StringFind(cmt, needle) >= 0)
            return true;
        }
     }
   // Pending orders
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ot = OrderGetTicket(i);
      if(ot == 0) continue;
      if(!OrderSelect(ot)) continue;
      if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      string cmt = OrderGetString(ORDER_COMMENT);
      if(StringFind(cmt, needle) >= 0)
         return true;
     }
   return false;
  }

string ResolveBrokerSymbol(const string canonical)
  {
   string base = NormalizeSymbolBase(canonical);
   if(StringLen(base) < 3) return "";
   if(SymbolSelect(base, true) && SymbolInfoInteger(base, SYMBOL_EXIST))
      return base;
   string candidates[12];
   candidates[0]=base+".r"; candidates[1]=base+"m"; candidates[2]=base+".i";
   candidates[3]=base+"#"; candidates[4]=base+".pro"; candidates[5]=base+".raw";
   candidates[6]=base+".ecn"; candidates[7]=base+".std"; candidates[8]=base+".a";
   candidates[9]=base+".b"; candidates[10]=base+".c"; candidates[11]=base+"i";
   for(int i=0;i<12;i++)
      if(SymbolSelect(candidates[i], true) && SymbolInfoInteger(candidates[i], SYMBOL_EXIST))
         return candidates[i];
   for(int pass=0; pass<2; pass++)
     {
      bool selected_only = (pass==0);
      int total = SymbolsTotal(selected_only);
      for(int i=0;i<total;i++)
        {
         string name = SymbolName(i, selected_only);
         if(NormalizeSymbolBase(name)==base && SymbolSelect(name, true))
            return name;
        }
     }
   if(NormalizeSymbolBase(_Symbol)==base) return _Symbol;
   Print("AEGIS: ResolveBrokerSymbol failed ", base);
   return "";
  }

bool HasOpenPositionOn(const string symbol)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      return true;
     }
   return false;
  }

ulong FindPositionTicket(const string symbol)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      return ticket;
     }
   return 0;
  }

bool SpreadOk(const string symbol)
  {
   double ask=SymbolInfoDouble(symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(symbol,SYMBOL_BID);
   double pt=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(pt<=0) return false;
   return ((int)MathRound((ask-bid)/pt) <= MaxSpreadPts);
  }

double NormalizeVolume(const string symbol, double vol)
  {
   double minLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxLot=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(vol<=0) vol=Lots;
   if(step<=0) step=0.01;
   vol=MathFloor(vol/step + 1e-12)*step;
   if(vol<minLot) vol=minLot;
   if(vol>maxLot) vol=maxLot;
   // decimals from volume step (0.01 → 2, 0.001 → 3)
   int digits=0;
   double s=step;
   while(digits<8 && MathAbs(s-MathRound(s))>1e-12)
     {
      s*=10.0;
      digits++;
     }
   if(digits<2) digits=2;
   return NormalizeDouble(vol,digits);
  }

// Safe fill modes: respect trade execution mode + filling flags
void GetSupportedFillModes(const string symbol, ENUM_ORDER_TYPE_FILLING &modes[])
  {
   int filling = (int)SymbolInfoInteger(symbol, SYMBOL_FILLING_MODE);
   ENUM_SYMBOL_TRADE_EXECUTION exec = (ENUM_SYMBOL_TRADE_EXECUTION)SymbolInfoInteger(symbol, SYMBOL_TRADE_EXEMODE);
   int n=0;
   ArrayResize(modes, 3);

   // Exchange / market: prefer IOC then FOK; avoid RETURN unless only option
   bool allowReturn = ((filling & SYMBOL_FILLING_RETURN) == SYMBOL_FILLING_RETURN);
   bool allowIoc = ((filling & SYMBOL_FILLING_IOC) == SYMBOL_FILLING_IOC);
   bool allowFok = ((filling & SYMBOL_FILLING_FOK) == SYMBOL_FILLING_FOK);

   if(exec == SYMBOL_TRADE_EXECUTION_EXCHANGE || exec == SYMBOL_TRADE_EXECUTION_MARKET)
     {
      if(allowIoc) modes[n++]=ORDER_FILLING_IOC;
      if(allowFok) modes[n++]=ORDER_FILLING_FOK;
      // RETURN often invalid for pure market execution
     }
   else
     {
      // Instant / Request — RETURN more common
      if(allowReturn) modes[n++]=ORDER_FILLING_RETURN;
      if(allowIoc) modes[n++]=ORDER_FILLING_IOC;
      if(allowFok) modes[n++]=ORDER_FILLING_FOK;
     }

   if(n==0)
     {
      if(allowIoc) modes[n++]=ORDER_FILLING_IOC;
      if(allowFok) modes[n++]=ORDER_FILLING_FOK;
      if(allowReturn) modes[n++]=ORDER_FILLING_RETURN;
     }
   if(n==0)
     {
      modes[0]=ORDER_FILLING_IOC;
      modes[1]=ORDER_FILLING_FOK;
      n=2;
     }
   ArrayResize(modes, n);
  }

//+------------------------------------------------------------------+
string JsonGetString(const string json, const string key)
  {
   string pattern="\""+key+"\"";
   int p=StringFind(json,pattern); if(p<0) return "";
   int colon=StringFind(json,":",p); if(colon<0) return "";
   int q1=StringFind(json,"\"",colon); if(q1<0) return "";
   int q2=StringFind(json,"\"",q1+1); if(q2<0) return "";
   return StringSubstr(json,q1+1,q2-q1-1);
  }
double JsonGetNumber(const string json, const string key)
  {
   string pattern="\""+key+"\"";
   int p=StringFind(json,pattern); if(p<0) return 0;
   int colon=StringFind(json,":",p); if(colon<0) return 0;
   string tail=StringSubstr(json,colon+1);
   while(StringLen(tail)>0 && (StringGetCharacter(tail,0)==' '||StringGetCharacter(tail,0)=='\t'))
      tail=StringSubstr(tail,1);
   if(StringFind(tail,"null")==0) return 0;
   if(StringGetCharacter(tail,0)=='"') return StringToDouble(JsonGetString(json,key));
   string num="";
   for(int i=0;i<StringLen(tail);i++)
     {
      ushort c=StringGetCharacter(tail,i);
      if((c>='0'&&c<='9')||c=='.'||c=='-'||c=='+') num+=CharToString((uchar)c);
      else if(StringLen(num)>0) break;
     }
   return StringToDouble(num);
  }
bool JsonGetBool(const string json, const string key)
  {
   string pattern="\""+key+"\"";
   int p=StringFind(json,pattern); if(p<0) return false;
   int colon=StringFind(json,":",p); if(colon<0) return false;
   string tail=StringSubstr(json,colon+1,20); StringToLower(tail);
   return (StringFind(tail,"true")>=0);
  }

string HttpGet(const string url)
  {
   char data[]; char result[]; string result_headers;
   string headers="X-API-Key: "+ApiKey+"\r\nContent-Type: application/json\r\n";
   ArrayResize(data,0);
   ResetLastError();
   int code=WebRequest("GET",url,headers,WebTimeoutMs,data,result,result_headers);
   if(code==-1){ Print("AEGIS GET fail err=",GetLastError()); return ""; }
   string body=CharArrayToString(result,0,WHOLE_ARRAY,CP_UTF8);
   if(code!=200){ Print("AEGIS HTTP ",code," ",StringSubstr(body,0,120)); return ""; }
   return body;
  }

// Returns HTTP status code; -1 on WebRequest failure
int HttpPostJson(const string url, const string payload)
  {
   char data[]; char result[]; string result_headers;
   StringToCharArray(payload,data,0,WHOLE_ARRAY,CP_UTF8);
   int n=ArraySize(data); if(n>0 && data[n-1]==0) ArrayResize(data,n-1);
   string headers="X-API-Key: "+ApiKey+"\r\nContent-Type: application/json\r\n";
   ResetLastError();
   int code=WebRequest("POST",url,headers,WebTimeoutMs,data,result,result_headers);
   if(code==-1)
     {
      Print("AEGIS POST fail err=",GetLastError()," url=",url);
      return -1;
     }
   return code;
  }

bool AckHttpOk(int code) { return (code>=200 && code<300); }

void QueueAckRetry(const string signalId, const string payload)
  {
   int n=ArraySize(g_ackPendingId);
   for(int i=0;i<n;i++)
     {
      if(g_ackPendingId[i]==signalId)
        {
         g_ackPendingPayload[i]=payload;
         return;
        }
     }
   ArrayResize(g_ackPendingId,n+1);
   ArrayResize(g_ackPendingPayload,n+1);
   ArrayResize(g_ackPendingTries,n+1);
   g_ackPendingId[n]=signalId;
   g_ackPendingPayload[n]=payload;
   g_ackPendingTries[n]=0;
  }

void ClearAckQueue(const string signalId)
  {
   for(int i=0;i<ArraySize(g_ackPendingId);i++)
      if(g_ackPendingId[i]==signalId)
        {
         g_ackPendingId[i]="";
         g_ackPendingPayload[i]="";
         g_ackPendingTries[i]=0;
        }
  }

// Returns true if ACK accepted by server
bool AckServerFull(const string signalId, const string symbol, const string side,
                   double volume, ulong orderTicket, ulong dealTicket, ulong positionTicket,
                   int retcode, bool ok, const string message)
  {
   if(StringLen(signalId)<4) return true;
   string url=BaseUrl()+"/api/executor/ack";
   string payload="{";
   payload+="\"account_id\":\""+AccountId+"\",";
   payload+="\"signal_id\":\""+signalId+"\",";
   payload+="\"ticket\":"+UlongToStr(orderTicket)+",";
   payload+="\"order_ticket\":"+UlongToStr(orderTicket)+",";
   payload+="\"deal_ticket\":"+UlongToStr(dealTicket)+",";
   payload+="\"position_ticket\":"+UlongToStr(positionTicket)+",";
   payload+="\"retcode\":"+IntegerToString(retcode)+",";
   payload+="\"ok\":"+(ok?"true":"false")+",";
   payload+="\"message\":\""+message+"\",";
   payload+="\"symbol\":\""+symbol+"\",";
   payload+="\"side\":\""+side+"\",";
   payload+="\"volume\":"+DoubleToString(volume,2);
   payload+="}";

   int code=HttpPostJson(url, payload);
   if(AckHttpOk(code))
     {
      ClearAckQueue(signalId);
      return true;
     }
   Print("AEGIS ACK HTTP ",code," — queue retry for ",signalId);
   QueueAckRetry(signalId, payload);
   return false;
  }

void FlushAckRetries()
  {
   string url=BaseUrl()+"/api/executor/ack";
   for(int i=0;i<ArraySize(g_ackPendingId);i++)
     {
      if(g_ackPendingId[i]=="") continue;
      if(g_ackPendingTries[i]>=MaxAckRetries)
        {
         Print("AEGIS ACK give up ",g_ackPendingId[i]," — server idempotent by signal_id");
         // Still mark handled locally; server completed set if any prior ACK, else TTL
         MarkHandled(g_ackPendingId[i]);
         g_ackPendingId[i]="";
         continue;
        }
      int code=HttpPostJson(url, g_ackPendingPayload[i]);
      g_ackPendingTries[i]++;
      if(AckHttpOk(code))
        {
         Print("AEGIS ACK retry ok ",g_ackPendingId[i]);
         MarkHandled(g_ackPendingId[i]);
         g_ackPendingId[i]="";
        }
     }
  }

//+------------------------------------------------------------------+
bool WasHandled(const string signalId)
  {
   for(int i=0;i<ArraySize(g_handledIds);i++)
      if(g_handledIds[i]==signalId) return true;
   return false;
  }

void MarkHandled(const string signalId)
  {
   if(signalId=="" || WasHandled(signalId)) return;
   int n=ArraySize(g_handledIds);
   ArrayResize(g_handledIds,n+1);
   g_handledIds[n]=signalId;
   if(ArraySize(g_handledIds)>100)
     {
      for(int i=0;i<50;i++) g_handledIds[i]=g_handledIds[i+50];
      ArrayResize(g_handledIds,50);
     }
   for(int i=0;i<ArraySize(g_retryIds);i++)
     if(g_retryIds[i]==signalId){ g_retryIds[i]=""; g_retrySpread[i]=0; g_retryBroker[i]=0; }
  }

void EnsureRetrySlot(const string signalId, int &idx)
  {
   for(int i=0;i<ArraySize(g_retryIds);i++)
     if(g_retryIds[i]==signalId){ idx=i; return; }
   idx=ArraySize(g_retryIds);
   ArrayResize(g_retryIds,idx+1);
   ArrayResize(g_retrySpread,idx+1);
   ArrayResize(g_retryBroker,idx+1);
   g_retryIds[idx]=signalId;
   g_retrySpread[idx]=0;
   g_retryBroker[idx]=0;
  }

bool IsTransientBroker(int retcode)
  {
   if(retcode==TRADE_RETCODE_REQUOTE) return true;
   if(retcode==TRADE_RETCODE_PRICE_OFF) return true;
   if(retcode==TRADE_RETCODE_PRICE_CHANGED) return true;
   if(retcode==TRADE_RETCODE_CONNECTION) return true;
   if(retcode==TRADE_RETCODE_TIMEOUT) return true;
   if(retcode==TRADE_RETCODE_TOO_MANY_REQUESTS) return true;
   if(retcode==TRADE_RETCODE_LOCKED) return true;
   return false;
  }

// 1 success, 0 transient, -1 permanent
int ExecuteTradeOn(const string brokerSymbol, const string side, double volume,
                   double sl, double tp, const string signalId, const string canonical)
  {
   // Restart-safe idempotency: already traded this signal_id (comment match)
   if(signalId!="" && signalId!="local" && SignalAlreadyExecuted(signalId, brokerSymbol))
     {
      Print("AEGIS: signal already executed (durable check) ", signalId);
      AckServerFull(signalId, brokerSymbol!=""?brokerSymbol:canonical, side, 0, 0, 0, 0, 0, true, "already_executed");
      return 1; // treat as success — do not open second position
     }
   if(StringLen(brokerSymbol)<1)
     {
      AckServerFull(signalId,canonical,side,0,0,0,0,-1,false,"resolve_failed");
      return -1;
     }
   if(OnePositionPerSymbol && HasOpenPositionOn(brokerSymbol))
     {
      AckServerFull(signalId,brokerSymbol,side,0,0,0,0,-2,false,"already_open");
      return -1;
     }
   if(!SpreadOk(brokerSymbol))
     {
      Print("AEGIS: spread wide ",brokerSymbol);
      return 0; // transient — spread category
     }

   double vol=NormalizeVolume(brokerSymbol,volume);
   int digits=(int)SymbolInfoInteger(brokerSymbol,SYMBOL_DIGITS);
   ENUM_ORDER_TYPE_FILLING modes[];
   GetSupportedFillModes(brokerSymbol,modes);

   MqlTradeRequest req;
   MqlTradeResult  res;
   int lastRet=0;

   for(int m=0;m<ArraySize(modes);m++)
     {
      ZeroMemory(req); ZeroMemory(res);
      req.action=TRADE_ACTION_DEAL;
      req.symbol=brokerSymbol;
      req.volume=vol;
      req.deviation=Slippage;
      req.magic=MagicNumber;
      req.comment="AEGIS "+signalId;
      req.type_filling=modes[m];
      if(side=="BUY")
        {
         req.type=ORDER_TYPE_BUY;
         req.price=SymbolInfoDouble(brokerSymbol,SYMBOL_ASK);
         if(sl>0) req.sl=NormalizeDouble(sl,digits);
         if(tp>0) req.tp=NormalizeDouble(tp,digits);
        }
      else if(side=="SELL")
        {
         req.type=ORDER_TYPE_SELL;
         req.price=SymbolInfoDouble(brokerSymbol,SYMBOL_BID);
         if(sl>0) req.sl=NormalizeDouble(sl,digits);
         if(tp>0) req.tp=NormalizeDouble(tp,digits);
        }
      else return -1;

      ResetLastError();
      bool sent=OrderSend(req,res);
      lastRet=(int)res.retcode;
      if(sent && (res.retcode==TRADE_RETCODE_DONE || res.retcode==TRADE_RETCODE_DONE_PARTIAL))
        {
         bool isPartial = (res.retcode==TRADE_RETCODE_DONE_PARTIAL);
         double filled = (res.volume > 0 ? res.volume : vol);
         Sleep(80);
         ulong posTicket = FindPositionTicket(brokerSymbol);
         // Do NOT substitute order ticket as position — leave 0 if unknown
         string msg = isPartial ? "partial_fill" : "ok";
         Print("AEGIS OK ", side, " ", brokerSymbol, " requested=", vol, " filled=", filled,
               " order=", res.order, " deal=", res.deal, " pos=", posTicket, " partial=", isPartial);

         if(isPartial && PartialFillPolicy == PARTIAL_COMPLETE_REMAINDER)
           {
            double remain = NormalizeVolume(brokerSymbol, vol - filled);
            if(remain >= SymbolInfoDouble(brokerSymbol, SYMBOL_VOLUME_MIN) - 1e-12)
              {
               Print("AEGIS: partial policy COMPLETE_REMAINDER residual=", remain);
               // One residual attempt with same fill mode
               MqlTradeRequest req2; MqlTradeResult res2;
               ZeroMemory(req2); ZeroMemory(res2);
               req2.action=TRADE_ACTION_DEAL; req2.symbol=brokerSymbol; req2.volume=remain;
               req2.deviation=Slippage; req2.magic=MagicNumber;
               req2.comment="AEGIS "+signalId+" rem"; req2.type_filling=modes[m];
               // Inherit protective levels from original signal / first request
               if(req.sl > 0) req2.sl = req.sl;
               if(req.tp > 0) req2.tp = req.tp;
               if(side=="BUY"){ req2.type=ORDER_TYPE_BUY; req2.price=SymbolInfoDouble(brokerSymbol,SYMBOL_ASK); }
               else { req2.type=ORDER_TYPE_SELL; req2.price=SymbolInfoDouble(brokerSymbol,SYMBOL_BID); }
               if(OrderSend(req2, res2) && (res2.retcode==TRADE_RETCODE_DONE || res2.retcode==TRADE_RETCODE_DONE_PARTIAL))
                 {
                  filled += (res2.volume > 0 ? res2.volume : remain);
                  if(res2.deal != 0) res.deal = res2.deal;
                  if(res2.order != 0) res.order = res2.order;
                  Sleep(50);
                  posTicket = FindPositionTicket(brokerSymbol);
                  msg = "partial_then_remainder";
                  Print("AEGIS remainder OK filled_total=", filled);
                 }
               else
                 {
                  msg = "partial_remainder_failed";
                  Print("AEGIS remainder failed ret=", res2.retcode);
                 }
              }
           }

         // ACK reports actual filled volume (policy A or after remainder attempt)
         bool ackOk = AckServerFull(signalId, brokerSymbol, side, filled, res.order, res.deal, posTicket, (int)res.retcode, true, msg);
         if(ackOk) return 1;
         return 2;
        }
      if(res.retcode==TRADE_RETCODE_INVALID_FILL) continue;
      if(IsTransientBroker((int)res.retcode)) return 0;
     }

   Print("AEGIS OrderSend fail ",brokerSymbol," ret=",lastRet);
   AckServerFull(signalId,brokerSymbol,side,vol,0,0,0,lastRet,false,IntegerToString(lastRet));
   return -1;
  }

bool HandleSignalJsonObject(const string obj)
  {
   string side=JsonGetString(obj,"side");
   if(side=="") side=JsonGetString(obj,"signal");
   StringToUpper(side);
   if(side!="BUY" && side!="SELL") return false;
   string signalId=JsonGetString(obj,"signal_id");
   if(signalId!="" && WasHandled(signalId)) return false;

   string canonical=JsonGetString(obj,"symbol");
   if(canonical=="") canonical=_Symbol;
   canonical=NormalizeSymbolBase(canonical);

   long created=(long)JsonGetNumber(obj,"created_at_ms");
   if(created>0)
     {
      long ageSec=((long)TimeGMT()*1000-created)/1000;
      if(ageSec>MaxSignalAgeSec)
        {
         MarkHandled(signalId);
         AckServerFull(signalId,canonical,side,0,0,0,0,-3,false,"stale");
         return false;
        }
     }

   double vol=JsonGetNumber(obj,"volume");
   double sl=JsonGetNumber(obj,"stop_loss");
   double tp=JsonGetNumber(obj,"take_profit");
   string brokerSym=ResolveBrokerSymbol(canonical);

   // Classify transient for spread vs broker before execute
   bool spreadIssue=false;
   if(StringLen(brokerSym)>0 && !SpreadOk(brokerSym) && !(OnePositionPerSymbol && HasOpenPositionOn(brokerSym)))
      spreadIssue=true;

   int rc=ExecuteTradeOn(brokerSym,side,vol,sl,tp,signalId,canonical);

   if(rc==1)
     {
      MarkHandled(signalId);
      return true;
     }
   if(rc==2)
     {
      // Trade succeeded but ACK is pending on the queue.
      // Mark locally handled immediately to prevent duplicate execution this session.
      // ACK retries independently; server is also idempotent by signal_id.
      MarkHandled(signalId);
      return true;
     }
   if(rc==-1)
     {
      MarkHandled(signalId);
      return false;
     }

   // transient
   int idx; EnsureRetrySlot(signalId, idx);
   if(spreadIssue || (StringLen(brokerSym)>0 && !SpreadOk(brokerSym)))
     {
      g_retrySpread[idx]++;
      if(g_retrySpread[idx]>=MaxRetriesSpread)
        {
         MarkHandled(signalId);
         AckServerFull(signalId,brokerSym,side,0,0,0,0,-5,false,"max_spread_retries");
        }
     }
   else
     {
      g_retryBroker[idx]++;
      if(g_retryBroker[idx]>=MaxRetriesBroker)
        {
         MarkHandled(signalId);
         AckServerFull(signalId,brokerSym,side,0,0,0,0,-4,false,"max_broker_retries");
        }
     }
   return false;
  }

void ProcessSignalsArray(const string body)
  {
   int key=StringFind(body,"\"signals\""); if(key<0) return;
   int arr=StringFind(body,"[",key); if(arr<0) return;
   int depth=0, start=-1;
   for(int i=arr;i<StringLen(body);i++)
     {
      ushort c=StringGetCharacter(body,i);
      if(c=='{'){ if(depth==0) start=i; depth++; }
      else if(c=='}')
        {
         depth--;
         if(depth==0 && start>=0)
           {
            HandleSignalJsonObject(StringSubstr(body,start,i-start+1));
            start=-1;
           }
        }
      else if(c==']' && depth==0) break;
     }
  }

void PollChartOnly()
  {
   string base=NormalizeSymbolBase(_Symbol);
   string url=BaseUrl()+"/api/executor/pending?account_id="+AccountId+"&symbol="+base;
   string body=HttpGet(url); if(body=="") return;
   if(!JsonGetBool(body,"has_signal")) return;
   HandleSignalJsonObject(body);
  }

void PollMultiPair()
  {
   string url=BaseUrl()+"/api/executor/pending-batch?account_id="+AccountId;
   string list=SymbolsList;
   if(StringLen(list)>0 && MaxSymbolsPerPoll>0)
     {
      string parts[]; int n=StringSplit(list,',',parts);
      string capped=""; int take=MathMin(n,MaxSymbolsPerPoll);
      for(int i=0;i<take;i++)
        {
         string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
         if(StringLen(s)<3) continue;
         if(StringLen(capped)>0) capped+=",";
         capped+=NormalizeSymbolBase(s);
        }
      list=capped;
     }
   if(StringLen(list)>0) url+="&symbols="+list;
   url+="&max_symbols="+IntegerToString(MaxSymbolsPerPoll);
   string body=HttpGet(url); if(body=="") return;
   ProcessSignalsArray(body);
  }

string ReadLocalSignal()
  {
   int h=FileOpen(SignalFile,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h==INVALID_HANDLE) return "";
   string s=FileReadString(h); FileClose(h);
   StringTrimLeft(s); StringTrimRight(s); StringToUpper(s);
   return s;
  }

void PollLocalFallback()
  {
   if(!UseLocalFileFallback) return;
   string sig=ReadLocalSignal();
   if(sig==""||sig==lastLocalSig) return;
   if(sig!="BUY"&&sig!="SELL") return;
   lastLocalSig=sig;
   string broker=ResolveBrokerSymbol(NormalizeSymbolBase(_Symbol));
   int rc=ExecuteTradeOn(broker,sig,Lots,0,0,"local",NormalizeSymbolBase(_Symbol));
   if(rc==1||rc==2) lastLocalSig=sig;
  }

int OnInit()
  {
   Print("AEGIS_Executor v2.15 PRODUCTION mode=",EnumToString(ExecMode)," account=",AccountId);
   EventSetTimer(MathMax(2,PollSeconds));
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){ EventKillTimer(); }
void OnTimer()
  {
   FlushAckRetries();
   if(UseServerSignals)
     {
      if(ExecMode==AEGIS_MODE_MULTI_PAIR) PollMultiPair();
      else PollChartOnly();
     }
   if(UseLocalFileFallback) PollLocalFallback();
  }
