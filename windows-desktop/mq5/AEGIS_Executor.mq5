//+------------------------------------------------------------------+
//| AEGIS_Executor.mq5                                               |
//| Reads latest signal file / HTTP poll and executes with risk mgmt |
//| Attach to the chart you trade. Compile in MetaEditor.            |
//+------------------------------------------------------------------+
#property copyright "LeverageFx / Honeydewnuts"
#property version   "1.00"
#property strict

input string ServerUrl   = "https://aegis-api-0z1p.onrender.com";
input string AccountId   = "";
input string ApiKey      = "";
input double Lots        = 0.01;
input int    Slippage    = 30;
input int    MagicNumber = 20260827;
input int    MaxSpreadPts = 40;
input int    PollSeconds  = 5;
input string SignalFile   = "aegis_signal.txt"; // optional local drop from Capture

datetime lastPoll = 0;
string   lastSignal = "";

//--- simple risk: one position per symbol
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(!PositionSelectByTicket(PositionGetTicket(i))) continue;
      if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      return true;
     }
   return false;
  }

bool SpreadOk()
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(pt <= 0) return false;
   int spread = (int)MathRound((ask - bid) / pt);
   return spread <= MaxSpreadPts;
  }

void ExecuteTrade(string side)
  {
   if(HasOpenPosition())
     {
      Print("AEGIS: position already open");
      return;
     }
   if(!SpreadOk())
     {
      Print("AEGIS: spread too wide");
      return;
     }
   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);
   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = Lots;
   req.deviation = Slippage;
   req.magic     = MagicNumber;
   req.type_filling = ORDER_FILLING_IOC;
   if(side == "BUY")
     {
      req.type = ORDER_TYPE_BUY;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
     }
   else if(side == "SELL")
     {
      req.type = ORDER_TYPE_SELL;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
     }
   else return;

   if(!OrderSend(req, res))
      Print("AEGIS OrderSend failed: ", GetLastError(), " retcode=", res.retcode);
   else
      Print("AEGIS trade ok: ", side, " ticket=", res.order);
  }

string ReadLocalSignal()
  {
   int h = FileOpen(SignalFile, FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h == INVALID_HANDLE) return "";
   string s = FileReadString(h);
   FileClose(h);
   StringTrimLeft(s);
   StringTrimRight(s);
   return s;
  }

int OnInit()
  {
   Print("AEGIS_Executor init. Server=", ServerUrl, " account=", AccountId);
   EventSetTimer(PollSeconds);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   string sig = ReadLocalSignal();
   if(sig == "" || sig == lastSignal) return;
   lastSignal = sig;
   if(sig == "BUY" || sig == "SELL")
      ExecuteTrade(sig);
  }

void OnTick()
  {
   // Optional: tighter reaction if signal file updated between timers
  }
