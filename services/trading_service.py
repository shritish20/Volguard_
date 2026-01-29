"""
Trading Service - Orchestrates analysis and execution
"""
from typing import Dict, Optional, List
from datetime import datetime
from models.domain import TradingMandate, VolMetrics, StructMetrics, EdgeMetrics, ExternalMetrics
from core.analytics import AnalyticsEngine
from core.regime import RegimeEngine
from core.calendar import CalendarEngine
from core.participant import ParticipantDataFetcher
from core.upstox import UpstoxFetcher
from database.repositories import AnalysisRepository, TradeRepository
from utils.logger import logger
from utils.telegram import telegram
from config import Config
import sqlite3

class TradingService:
    """Main trading orchestration service"""
    
    def __init__(self, db_conn: sqlite3.Connection):
        self.db_conn = db_conn
        self.analysis_repo = AnalysisRepository(db_conn)
        self.trade_repo = TradeRepository(db_conn)
        self.upstox = UpstoxFetcher()
        self.analytics = AnalyticsEngine(self.upstox)
    
    def run_full_analysis(self) -> Optional[Dict]:
        """
        Run complete market analysis
        Returns all mandates and metrics
        """
        try:
            logger.info("🔄 Running full market analysis...")
            
            # 1. Economic Calendar (veto check)
            calendar_events = CalendarEngine.fetch_calendar(days_ahead=7)
            has_veto, veto_name, square_off_needed, hours_until = CalendarEngine.analyze_veto_risk(calendar_events)
            
            veto_reasons = []
            if has_veto and square_off_needed:
                veto_reasons.append(f"{veto_name} in {hours_until:.1f}h - SQUARE OFF RECOMMENDED")
                logger.warning(f"⛔ VETO EVENT: {veto_name}")
                telegram.send(f"⛔ Veto Event: {veto_name}\nSquare off by {hours_until:.0f}h", "WARNING")
            
            # 2. Get all metrics
            vol_metrics = self.analytics.get_vol_metrics()
            if not vol_metrics:
                logger.error("Failed to get vol metrics")
                return None
            
            struct_metrics = self.analytics.get_struct_metrics()
            if not struct_metrics:
                logger.error("Failed to get struct metrics")
                return None
            
            edge_metrics = self.analytics.get_edge_metrics()
            if not edge_metrics:
                logger.error("Failed to get edge metrics")
                return None
            
            # 3. External data
            fii_net, dii_net, fii_context = ParticipantDataFetcher.fetch_smart_participant_data()
            external_metrics = ExternalMetrics(
                fii_net=fii_net,
                fii_context=fii_context,
                dii_net=dii_net
            )
            
            # 4. Calculate scores
            score = RegimeEngine.calculate_scores(
                vol_metrics, struct_metrics, edge_metrics, external_metrics
            )
            
            # 5. Dynamic weights
            dynamic_weights = RegimeEngine.calculate_dynamic_weights(vol_metrics, struct_metrics)
            
            # 6. Generate mandates
            weekly_mandate = RegimeEngine.generate_mandate(
                expiry_type="WEEKLY",
                score=score,
                vol_metrics=vol_metrics,
                veto_reasons=veto_reasons,
                dynamic_weights=dynamic_weights
            )
            
            monthly_mandate = RegimeEngine.generate_mandate(
                expiry_type="MONTHLY",
                score=score,
                vol_metrics=vol_metrics,
                veto_reasons=veto_reasons,
                dynamic_weights=dynamic_weights
            )
            
            # 7. Package results
            analysis_result = {
                'timestamp': datetime.now().isoformat(),
                'weekly_mandate': self._mandate_to_dict(weekly_mandate),
                'monthly_mandate': self._mandate_to_dict(monthly_mandate),
                'vol_metrics': self._vol_metrics_to_dict(vol_metrics),
                'struct_metrics': self._struct_metrics_to_dict(struct_metrics),
                'edge_metrics': self._edge_metrics_to_dict(edge_metrics),
                'external_metrics': self._external_metrics_to_dict(external_metrics),
                'veto_events': [self._event_to_dict(e) for e in calendar_events if e.is_veto_event],
                'regime_name': weekly_mandate.regime_name
            }
            
            # 8. Save to database
            self.analysis_repo.save_analysis(analysis_result)
            
            logger.info(f"✅ Analysis complete: {weekly_mandate.regime_name} ({score.composite:.1f}/100)")
            telegram.send(
                f"Analysis Complete\n"
                f"Regime: {weekly_mandate.regime_name}\n"
                f"Score: {score.composite:.1f}\n"
                f"Weekly: {weekly_mandate.suggested_structure}\n"
                f"Monthly: {monthly_mandate.suggested_structure}",
                "SUCCESS"
            )
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            telegram.send(f"Analysis failed: {str(e)}", "ERROR")
            return None
    
    def _mandate_to_dict(self, m: TradingMandate) -> Dict:
        """Convert mandate to dict"""
        return {
            'expiry_type': m.expiry_type,
            'regime_name': m.regime_name,
            'suggested_structure': m.suggested_structure,
            'directional_bias': m.directional_bias,
            'allocation_pct': m.allocation_pct,
            'deployment_amount': m.deployment_amount,
            'max_lots': m.max_lots,
            'score': {
                'composite': m.score.composite,
                'confidence': m.score.confidence,
                'vol_score': m.score.vol_score,
                'struct_score': m.score.struct_score,
                'edge_score': m.score.edge_score,
                'risk_score': m.score.risk_score,
                'vol_drivers': m.score.vol_drivers,
                'struct_drivers': m.score.struct_drivers,
                'edge_drivers': m.score.edge_drivers,
                'risk_factors': m.score.risk_factors
            },
            'rationale': m.rationale,
            'warnings': m.warnings,
            'veto_reasons': m.veto_reasons,
            'dynamic_weights': m.dynamic_weights
        }
    
    def _vol_metrics_to_dict(self, v: VolMetrics) -> Dict:
        """Convert vol metrics to dict"""
        return {
            'spot_price': v.spot_price,
            'vix': v.vix,
            'vix_change_pct': v.vix_change_pct,
            'iv_percentile': v.iv_percentile,
            'iv_rank': v.iv_rank,
            'historical_vol_20d': v.historical_vol_20d,
            'garch_forecast': v.garch_forecast,
            'parkinson_vol': v.parkinson_vol,
            'vov': v.vov,
            'vov_zscore': v.vov_zscore,
            'vix_momentum': v.vix_momentum
        }
    
    def _struct_metrics_to_dict(self, s: StructMetrics) -> Dict:
        return {
            'gamma_exposure': s.gamma_exposure,
            'put_call_ratio': s.put_call_ratio,
            'skew_25delta': s.skew_25delta,
            'max_pain': s.max_pain,
            'atm_iv': s.atm_iv
        }
    
    def _edge_metrics_to_dict(self, e: EdgeMetrics) -> Dict:
        return {
            'vrp': e.vrp,
            'term_structure_edge': e.term_structure_edge,
            'smart_expiry_weekly': e.smart_expiry_weekly,
            'smart_expiry_monthly': e.smart_expiry_monthly
        }
    
    def _external_metrics_to_dict(self, e: ExternalMetrics) -> Dict:
        return {
            'fii_net': e.fii_net,
            'fii_context': e.fii_context,
            'dii_net': e.dii_net
        }
    
    def _event_to_dict(self, e) -> Dict:
        return {
            'title': e.title,
            'country': e.country,
            'event_date': e.event_date.isoformat(),
            'impact_level': e.impact_level,
            'hours_until': e.hours_until,
            'is_veto_event': e.is_veto_event
        }
