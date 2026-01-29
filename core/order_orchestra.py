"""
VolGuard 3.3 - Order Orchestrator
Multi-leg order execution with status polling and rollback
"""
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import upstox_client
from upstox_client.api.order_api import OrderApi
from config import Config
from utils.logger import logger
from utils.telegram import telegram
from database.repositories import TradeRepository, OrderRepository


class OrderOrchestrator:
    """
    Orchestrates multi-leg order execution with polling and error handling
    """
    
    def __init__(self, db_conn):
        """
        Args:
            db_conn: Database connection
        """
        self.db_conn = db_conn
        self.trade_repo = TradeRepository(db_conn)
        self.order_repo = OrderRepository(db_conn)
        
        # Initialize Upstox API
        configuration = upstox_client.Configuration()
        configuration.access_token = Config.UPSTOX_ACCESS_TOKEN
        api_client = upstox_client.ApiClient(configuration)
        self.order_api = OrderApi(api_client)
    
    def execute_strategy(
        self,
        legs: List[Dict],
        strategy_name: str,
        mandate_data: Dict
    ) -> Optional[str]:
        """
        Execute complete multi-leg strategy
        
        Args:
            legs: List of leg dictionaries with side, strike, quantity, etc.
            strategy_name: Strategy name (e.g., "IRON_FLY")
            mandate_data: Mandate information for tracking
            
        Returns:
            str: trade_id if successful, None if failed
        """
        logger.info(f"🚀 Executing {strategy_name} with {len(legs)} legs")
        
        # 1. Create trade record
        trade_id = self._generate_trade_id()
        
        try:
            # Save initial trade record
            self.trade_repo.create_trade(
                trade_id=trade_id,
                strategy=strategy_name,
                expiry_type=mandate_data.get("expiry_type", "WEEKLY"),
                expiry_date=legs[0].get("expiry"),
                status="PENDING",
                entry_time=datetime.now().isoformat()
            )
            
            # 2. Execute legs sequentially
            executed_legs = []
            failed_leg_index = None
            
            for i, leg in enumerate(legs):
                logger.info(f"📊 Executing leg {i+1}/{len(legs)}: {leg['side']} {leg['strike']} {leg['option_type']}")
                
                success, result = self._execute_leg(leg, trade_id)
                
                if success:
                    executed_legs.append(result)
                    
                    # Save leg to database
                    self.order_repo.save_leg(trade_id, result)
                    
                    logger.info(f"✅ Leg {i+1} filled: {result['filled_qty']} @ {result['entry_price']}")
                else:
                    failed_leg_index = i
                    logger.error(f"❌ Leg {i+1} failed: {result}")
                    break
            
            # 3. Check if all legs executed
            if failed_leg_index is not None:
                logger.error(f"⚠️ Strategy execution failed at leg {failed_leg_index + 1}, rolling back...")
                telegram.send(
                    f"Strategy execution failed at leg {failed_leg_index + 1}\n"
                    f"Strategy: {strategy_name}\n"
                    f"Rolling back {len(executed_legs)} executed legs",
                    "ERROR"
                )
                
                # Rollback executed legs
                self._rollback_executed_legs(executed_legs, trade_id)
                
                # Update trade status
                self.trade_repo.update_trade_status(trade_id, "FAILED")
                
                return None
            
            # 4. Calculate entry metrics
            entry_credit = self._calculate_entry_credit(executed_legs)
            max_loss = self._calculate_max_loss(executed_legs)
            
            # 5. Update trade record
            self.trade_repo.update_trade(
                trade_id=trade_id,
                status="OPEN",
                entry_credit=entry_credit,
                max_loss=max_loss,
                legs=executed_legs
            )
            
            logger.info(f"✅ Strategy executed successfully: {trade_id}")
            logger.info(f"   Entry Credit: ₹{entry_credit:,.0f}")
            logger.info(f"   Max Loss: ₹{max_loss:,.0f}")
            
            telegram.send(
                f"✅ Trade Opened\n"
                f"Strategy: {strategy_name}\n"
                f"Trade ID: {trade_id}\n"
                f"Legs: {len(executed_legs)}\n"
                f"Entry Credit: ₹{entry_credit:,.0f}\n"
                f"Max Loss: ₹{max_loss:,.0f}",
                "TRADE"
            )
            
            return trade_id
            
        except Exception as e:
            logger.error(f"Strategy execution error: {e}", exc_info=True)
            telegram.send(f"Strategy execution error: {str(e)}", "ERROR")
            
            # Update trade status
            self.trade_repo.update_trade_status(trade_id, "FAILED")
            
            return None
    
    def _execute_leg(self, leg: Dict, trade_id: str) -> Tuple[bool, Dict]:
        """
        Execute single leg with status polling
        
        Args:
            leg: Leg specification
            trade_id: Parent trade ID
            
        Returns:
            Tuple[bool, Dict]: (success, result_dict)
        """
        try:
            # 1. Place order
            order_id = self._place_order(leg)
            
            if not order_id:
                return False, {"error": "Failed to place order"}
            
            logger.info(f"   Order placed: {order_id}")
            
            # 2. Poll for order status
            start_time = time.time()
            timeout = Config.ORDER_TIMEOUT
            poll_interval = Config.POLL_INTERVAL
            
            while True:
                elapsed = time.time() - start_time
                
                if elapsed > timeout:
                    logger.error(f"   Order timeout after {timeout}s")
                    
                    # Cancel order
                    self._cancel_order(order_id)
                    
                    return False, {"error": "Order timeout", "order_id": order_id}
                
                # Get order status
                status_dict = self._get_order_status(order_id)
                
                if not status_dict:
                    time.sleep(poll_interval)
                    continue
                
                status = status_dict.get("status", "").upper()
                
                # Check if filled
                if status == "COMPLETE":
                    filled_qty = status_dict.get("filled_quantity", 0)
                    total_qty = leg["quantity"]
                    
                    # Check partial fills
                    fill_ratio = filled_qty / total_qty if total_qty > 0 else 0
                    
                    if fill_ratio < Config.PARTIAL_FILL_TOLERANCE:
                        logger.warning(f"   Partial fill: {filled_qty}/{total_qty} ({fill_ratio:.1%})")
                        
                        # For BUY (hedges), require high fill ratio
                        if leg["side"] == "BUY" and fill_ratio < Config.HEDGE_FILL_TOLERANCE:
                            logger.error(f"   Insufficient hedge fill: {fill_ratio:.1%}")
                            return False, {"error": "Insufficient hedge fill", "order_id": order_id}
                    
                    # Calculate slippage
                    avg_price = status_dict.get("average_price", leg["ltp"])
                    slippage_pct = abs(avg_price - leg["ltp"]) / leg["ltp"] if leg["ltp"] > 0 else 0
                    
                    if slippage_pct > Config.SLIPPAGE_TOLERANCE:
                        logger.warning(f"   High slippage: {slippage_pct:.2%}")
                    
                    # Success
                    result = {
                        "order_id": order_id,
                        "instrument_key": leg["instrument_key"],
                        "side": leg["side"],
                        "option_type": leg["option_type"],
                        "strike": leg["strike"],
                        "quantity": total_qty,
                        "filled_qty": filled_qty,
                        "entry_price": avg_price,
                        "expected_price": leg["ltp"],
                        "slippage_pct": slippage_pct,
                        "fill_time": datetime.now().isoformat(),
                        "elapsed_seconds": elapsed,
                        "role": leg.get("role", "UNKNOWN"),
                        "expiry": leg.get("expiry")
                    }
                    
                    return True, result
                
                # Check if rejected
                elif status in ["REJECTED", "CANCELLED"]:
                    logger.error(f"   Order {status}: {status_dict.get('status_message', 'Unknown')}")
                    return False, {
                        "error": f"Order {status}",
                        "order_id": order_id,
                        "message": status_dict.get('status_message')
                    }
                
                # Continue polling
                time.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Leg execution error: {e}", exc_info=True)
            return False, {"error": str(e)}
    
    def _place_order(self, leg: Dict) -> Optional[str]:
        """
        Place order via Upstox API
        
        Args:
            leg: Leg specification
            
        Returns:
            str: Order ID or None
        """
        try:
            # Construct order request
            order_data = upstox_client.PlaceOrderRequest(
                quantity=int(leg["quantity"]),
                product="D",  # Delivery (for options)
                validity="DAY",
                price=0,  # Market order
                tag="volguard",
                instrument_token=leg["instrument_key"],
                order_type="MARKET",
                transaction_type="BUY" if leg["side"] == "BUY" else "SELL",
                disclosed_quantity=0,
                trigger_price=0,
                is_amo=False
            )
            
            # Place order
            api_response = self.order_api.place_order(order_data)
            
            if api_response.status == "success":
                order_id = api_response.data.order_id
                return order_id
            else:
                logger.error(f"Order placement failed: {api_response}")
                return None
            
        except Exception as e:
            logger.error(f"Order placement error: {e}", exc_info=True)
            return None
    
    def _get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get order status from Upstox
        
        Args:
            order_id: Order ID
            
        Returns:
            Dict: Order status or None
        """
        try:
            api_response = self.order_api.get_order_details(order_id)
            
            if api_response.status == "success" and api_response.data:
                order = api_response.data[0]  # Get first order
                
                return {
                    "order_id": order.order_id,
                    "status": order.status,
                    "status_message": order.status_message,
                    "filled_quantity": order.filled_quantity,
                    "average_price": order.average_price,
                    "order_timestamp": order.order_timestamp
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None
    
    def _cancel_order(self, order_id: str) -> bool:
        """
        Cancel order
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: True if cancelled
        """
        try:
            api_response = self.order_api.cancel_order(order_id)
            
            if api_response.status == "success":
                logger.info(f"   Order cancelled: {order_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return False
    
    def _rollback_executed_legs(self, executed_legs: List[Dict], trade_id: str):
        """
        Rollback executed legs by placing reverse orders
        
        Args:
            executed_legs: List of executed leg dicts
            trade_id: Trade ID
        """
        logger.warning(f"🔄 Rolling back {len(executed_legs)} executed legs")
        
        for leg in executed_legs:
            try:
                # Reverse the leg
                reverse_leg = {
                    "side": "SELL" if leg["side"] == "BUY" else "BUY",
                    "instrument_key": leg["instrument_key"],
                    "option_type": leg["option_type"],
                    "strike": leg["strike"],
                    "quantity": leg["filled_qty"],
                    "ltp": leg["entry_price"],  # Use entry price as reference
                    "role": f"ROLLBACK_{leg['role']}"
                }
                
                # Execute reverse
                success, result = self._execute_leg(reverse_leg, trade_id)
                
                if success:
                    logger.info(f"   Rolled back: {leg['strike']} {leg['option_type']}")
                else:
                    logger.error(f"   Rollback failed for: {leg['strike']} {leg['option_type']}")
                    telegram.send(
                        f"⚠️ Rollback failed for {leg['strike']} {leg['option_type']}\n"
                        f"Manual intervention required!",
                        "CRITICAL"
                    )
                
            except Exception as e:
                logger.error(f"Rollback error: {e}", exc_info=True)
    
    def exit_strategy(self, trade_id: str, reason: str = "MANUAL") -> bool:
        """
        Exit entire strategy by closing all legs
        
        Args:
            trade_id: Trade ID to exit
            reason: Exit reason
            
        Returns:
            bool: True if successful
        """
        logger.info(f"🚪 Exiting trade {trade_id}, reason: {reason}")
        
        try:
            # 1. Get trade legs
            trade = self.trade_repo.get_trade(trade_id)
            
            if not trade:
                logger.error(f"Trade not found: {trade_id}")
                return False
            
            if trade["status"] != "OPEN":
                logger.warning(f"Trade is not open: {trade['status']}")
                return False
            
            legs = trade.get("legs", [])
            
            if not legs:
                logger.error("No legs found for trade")
                return False
            
            # 2. Execute reverse orders
            exit_legs = []
            
            for leg in legs:
                reverse_leg = {
                    "side": "SELL" if leg["side"] == "BUY" else "BUY",
                    "instrument_key": leg["instrument_key"],
                    "option_type": leg["option_type"],
                    "strike": leg["strike"],
                    "quantity": leg["filled_qty"],
                    "ltp": 0,  # Will fetch current price
                    "role": f"EXIT_{leg['role']}"
                }
                
                # Get current LTP
                from core.upstox import UpstoxFetcher
                upstox = UpstoxFetcher()
                current_ltp = upstox.get_ltp(leg["instrument_key"])
                
                if current_ltp:
                    reverse_leg["ltp"] = current_ltp
                else:
                    logger.warning(f"Failed to get LTP for {leg['instrument_key']}, using entry price")
                    reverse_leg["ltp"] = leg["entry_price"]
                
                # Execute
                success, result = self._execute_leg(reverse_leg, trade_id)
                
                if success:
                    exit_legs.append(result)
                else:
                    logger.error(f"Failed to exit leg: {leg['strike']} {leg['option_type']}")
                    # Continue with other legs
            
            # 3. Calculate P&L
            realized_pnl = self._calculate_realized_pnl(legs, exit_legs)
            
            # 4. Update trade record
            self.trade_repo.update_trade(
                trade_id=trade_id,
                status="CLOSED",
                exit_time=datetime.now().isoformat(),
                exit_reason=reason,
                realized_pnl=realized_pnl,
                exit_legs=exit_legs
            )
            
            logger.info(f"✅ Trade closed: {trade_id}, P&L: ₹{realized_pnl:,.0f}")
            
            telegram.send(
                f"✅ Trade Closed\n"
                f"Trade ID: {trade_id}\n"
                f"Reason: {reason}\n"
                f"Realized P&L: ₹{realized_pnl:,.0f}",
                "TRADE"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Exit strategy error: {e}", exc_info=True)
            return False
    
    def _calculate_entry_credit(self, legs: List[Dict]) -> float:
        """Calculate net entry credit/debit"""
        net = 0
        lot_size = 25  # Nifty lot size
        
        for leg in legs:
            price = leg["entry_price"]
            qty = leg["filled_qty"]
            
            if leg["side"] == "SELL":
                net += price * qty * lot_size
            else:  # BUY
                net -= price * qty * lot_size
        
        return net
    
    def _calculate_max_loss(self, legs: List[Dict]) -> float:
        """Calculate maximum loss for strategy"""
        # Simplified: For spreads, max loss = width - credit
        # For now, return a conservative estimate
        
        # Find strikes
        strikes = [leg["strike"] for leg in legs]
        
        if not strikes:
            return 0
        
        # Max spread width
        max_width = max(strikes) - min(strikes)
        
        # Calculate net credit
        net_credit = self._calculate_entry_credit(legs)
        
        # Max loss = width - credit (for credit spreads)
        lot_size = 25
        max_lots = max([leg["filled_qty"] for leg in legs])
        
        max_loss = (max_width * lot_size * max_lots) - net_credit
        
        return max(max_loss, 0)
    
    def _calculate_realized_pnl(self, entry_legs: List[Dict], exit_legs: List[Dict]) -> float:
        """Calculate realized P&L"""
        lot_size = 25
        pnl = 0
        
        for entry_leg in entry_legs:
            # Find matching exit leg
            exit_leg = next(
                (el for el in exit_legs if el["instrument_key"] == entry_leg["instrument_key"]),
                None
            )
            
            if not exit_leg:
                logger.warning(f"No exit leg found for {entry_leg['instrument_key']}")
                continue
            
            entry_price = entry_leg["entry_price"]
            exit_price = exit_leg["entry_price"]
            qty = entry_leg["filled_qty"]
            
            if entry_leg["side"] == "SELL":
                # Sold at entry, bought at exit
                pnl += (entry_price - exit_price) * qty * lot_size
            else:  # BUY
                # Bought at entry, sold at exit
                pnl += (exit_price - entry_price) * qty * lot_size
        
        return pnl
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"VG_{timestamp}"


# Repository additions needed
class OrderRepository:
    """Order repository for saving leg details"""
    
    def __init__(self, db_conn):
        self.conn = db_conn
    
    def save_leg(self, trade_id: str, leg: Dict):
        """Save executed leg"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO trade_legs (
                    trade_id, order_id, instrument_key, side, option_type,
                    strike, quantity, filled_qty, entry_price, expected_price,
                    slippage_pct, fill_time, role
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id, leg["order_id"], leg["instrument_key"], leg["side"],
                leg["option_type"], leg["strike"], leg["quantity"], leg["filled_qty"],
                leg["entry_price"], leg["expected_price"], leg["slippage_pct"],
                leg["fill_time"], leg["role"]
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving leg: {e}")
