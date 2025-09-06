import csv
import io
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SanctionsScreeningEngine:
    def __init__(self):
        # Dummy sanctions data for demonstration
        # In a real application, this would come from a database or external API
        self.DUMMY_SANCTIONS_LIST = [
            {"name": "John Doe", "country": "USA", "entity_type": "Individual", "sanctioned": True, "pep": False, "adverse_media": ["Fraud allegations"]},
            {"name": "Jane Smith", "country": "UK", "entity_type": "Individual", "sanctioned": False, "pep": True, "adverse_media": ["Political exposure"]},
            {"name": "Global Corp", "country": "Germany", "entity_type": "Company", "sanctioned": True, "pep": False, "adverse_media": ["Environmental violations"]},
            {"name": "Acme Inc", "country": "USA", "entity_type": "Company", "sanctioned": False, "pep": False, "adverse_media": []},
            {"name": "Robert Johnson", "country": "Canada", "entity_type": "Individual", "sanctioned": True, "pep": False, "adverse_media": ["Terrorism financing"]},
            {"name": "Maria Garcia", "country": "Mexico", "entity_type": "Individual", "sanctioned": False, "pep": True, "adverse_media": ["Public official"]},
        ]

    async def screen_transaction(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        logger.info(f"[SanctionsScreeningEngine] screen_transaction called with data: {transaction_data}")
        """
        Screens a transaction's counterparty against sanctions lists.
        In a real scenario, this would involve more sophisticated matching algorithms
        and external data sources.
        """
        counterparty_name = transaction_data.get("counterparty_name")
        counterparty_country = transaction_data.get("counterparty_country") # Assuming this might be in transaction_data

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

        # Simple exact match for demonstration
        for entry in self.DUMMY_SANCTIONS_LIST:
            name_match = counterparty_name.lower() == entry["name"].lower()
            country_match = (counterparty_country is None or 
                             (entry.get("country") and counterparty_country.lower() == entry["country"].lower()))

            logger.info(f"[SanctionsScreeningEngine] Comparing '{counterparty_name}' ('{counterparty_country}') with '{entry['name']}' ('{entry.get('country')}'). Name match: {name_match}, Country match: {country_match}")

            if name_match and country_match:
                matched = True
                if entry["sanctioned"]:
                    sanctions_matches.append({
                        "matched_name": entry["name"],
                        "entity_type": entry["entity_type"],
                        "similarity_score": 1.0 # Perfect match for dummy data
                    })
                    risk_score = max(risk_score, 0.9) # High risk for sanctions hit
                    details += f"Sanctioned match: {entry['name']}. "
                if entry["pep"]:
                    pep_matches.append({
                        "matched_name": entry["name"],
                        "entity_type": "PEP",
                        "similarity_score": 1.0 # Perfect match for dummy data
                    })
                    risk_score = max(risk_score, 0.7) # Medium-high risk for PEP
                    details += f"PEP match: {entry['name']}. "
                if entry["adverse_media"]:
                    adverse_media_hits.extend(entry["adverse_media"])
                    risk_score = max(risk_score, 0.8) # High risk for adverse media
                    details += f"Adverse media hits for {entry['name']}. "
        
        if not matched:
            details = f"No sanctions, PEP, or adverse media matches found for {counterparty_name}."

        final_result = {
            "matched": matched,
            "matches": sanctions_matches, # This will be used by main.py for general matches
            "pep_matches": pep_matches,
            "adverse_media_hits": adverse_media_hits,
            "risk_score": risk_score,
            "details": details.strip()
        }
        logger.info(f"[SanctionsScreeningEngine] Returning result: {final_result}")
        return final_result
