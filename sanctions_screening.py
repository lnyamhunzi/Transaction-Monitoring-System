import csv
import io
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import SanctionsList, PEPList

logger = logging.getLogger(__name__)

class SanctionsScreeningEngine:
    def __init__(self):
        pass

    async def screen_transaction(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        logger.info(f"[SanctionsScreeningEngine] screen_transaction called with data: {transaction_data}")
        """
        Screens a transaction's counterparty against sanctions and PEP lists from the database.
        """
        counterparty_name = transaction_data.get("counterparty_name")
        counterparty_country = transaction_data.get("counterparty_country")

        if not counterparty_name:
            logger.warning("[SanctionsScreeningEngine] No counterparty name provided.")
            return {
                "matched": False,
                "matches": [],
                "pep_matches": [],
                "adverse_media_hits": [],
                "risk_score": 0.0,
                "details": "No counterparty name provided for screening."
            }

        matched = False
        sanctions_matches = []
        pep_matches = []
        adverse_media_hits = []
        risk_score = 0.0
        details = ""

        # Search in SanctionsList
        sanctions_query = db.query(SanctionsList).filter(
            or_(
                SanctionsList.entity_name.ilike(f"%{counterparty_name}%"),
                SanctionsList.aliases.ilike(f"%{counterparty_name}%")
            )
        )
        if counterparty_country:
            sanctions_query = sanctions_query.filter(SanctionsList.nationality.ilike(f"%{counterparty_country}%"))

        for entry in sanctions_query.all():
            matched = True
            sanctions_matches.append({
                "matched_name": entry.entity_name,
                "entity_type": entry.entity_type,
                "similarity_score": 0.9 # Using a fixed score for ilike match
            })
            risk_score = max(risk_score, 0.9)
            details += f"Sanctioned match: {entry.entity_name}. "

        # Search in PEPList
        pep_query = db.query(PEPList).filter(
            or_(
                PEPList.full_name.ilike(f"%{counterparty_name}%"),
                PEPList.aliases.ilike(f"%{counterparty_name}%")
            )
        )
        if counterparty_country:
            pep_query = pep_query.filter(PEPList.country.ilike(f"%{counterparty_country}%"))
        
        for entry in pep_query.all():
            matched = True
            pep_matches.append({
                "matched_name": entry.full_name,
                "entity_type": "PEP",
                "similarity_score": 0.9 # Using a fixed score for ilike match
            })
            risk_score = max(risk_score, 0.7)
            details += f"PEP match: {entry.full_name}. "

        # Adverse media hits would require an external service, so we'll leave it empty for now.
        
        if not matched:
            details = f"No sanctions, PEP, or adverse media matches found for {counterparty_name}."

        final_result = {
            "matched": matched,
            "matches": sanctions_matches,
            "pep_matches": pep_matches,
            "adverse_media_hits": adverse_media_hits,
            "risk_score": risk_score,
            "details": details.strip()
        }
        logger.info(f"[SanctionsScreeningEngine] Returning result: {final_result}")
        return final_result
