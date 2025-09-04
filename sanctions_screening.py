"""
Sanctions Screening Engine with fuzzy matching capabilities
"""

import logging
import re
from typing import Dict, Any, List, Tuple
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from models import SanctionsList, PEPList, Customer

logger = logging.getLogger(__name__)

class SanctionsScreeningEngine:
    """Advanced sanctions screening with fuzzy matching"""
    
    def __init__(self):
        self.similarity_threshold = 0.8
        self.phonetic_threshold = 0.85
        
        # Common name variations and abbreviations
        self.name_variations = {
            'COMPANY': ['CO', 'CORP', 'CORPORATION', 'LTD', 'LIMITED', 'INC', 'INCORPORATED'],
            'BANK': ['BK', 'BANKING', 'BANQUE', 'BANCO'],
            'INTERNATIONAL': ['INTL', 'INT\'L', 'INTERNATIONAL'],
            'FOUNDATION': ['FOUND', 'FDN'],
            'ASSOCIATION': ['ASSOC', 'ASSN'],
            'ORGANIZATION': ['ORG', 'ORGN']
        }
        
        # Common transliterations
        self.transliterations = {
            'KH': 'H', 'PH': 'F', 'QU': 'KW', 'X': 'KS',
            'Z': 'S', 'C': 'K', 'Y': 'I', 'J': 'I'
        }
    
    async def screen_transaction(self, transaction_data: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """Screen transaction against sanctions and PEP lists"""
        try:
            customer_id = transaction_data.get('customer_id')
            counterparty_name = transaction_data.get('counterparty_name', '')
            counterparty_bank = transaction_data.get('counterparty_bank', '')
            
            # Get customer information
            customer = db.query(Customer).filter(Customer.customer_id == customer_id).first()
            
            screening_results = {
                'matched': False,
                'matches': [],
                'risk_score': 0.0,
                'details': ''
            }
            
            entities_to_screen = []
            
            # Add customer for screening
            if customer:
                entities_to_screen.append({
                    'name': customer.full_name,
                    'type': 'CUSTOMER',
                    'date_of_birth': customer.date_of_birth,
                    'nationality': customer.nationality
                })
            
            # Add counterparty for screening
            if counterparty_name:
                entities_to_screen.append({
                    'name': counterparty_name,
                    'type': 'COUNTERPARTY',
                    'date_of_birth': None,
                    'nationality': None
                })
            
            # Add counterparty bank for screening
            if counterparty_bank:
                entities_to_screen.append({
                    'name': counterparty_bank,
                    'type': 'BANK',
                    'date_of_birth': None,
                    'nationality': None
                })
            
            # Screen each entity
            for entity in entities_to_screen:
                # Screen against sanctions lists
                sanctions_matches = await self.screen_against_sanctions(entity, db)
                
                # Screen against PEP lists
                pep_matches = await self.screen_against_peps(entity, db)
                
                # Combine results
                all_matches = sanctions_matches + pep_matches
                
                if all_matches:
                    screening_results['matched'] = True
                    screening_results['matches'].extend(all_matches)
                    
                    # Calculate risk score based on match quality
                    max_score = max(match['similarity_score'] for match in all_matches)
                    screening_results['risk_score'] = max(screening_results['risk_score'], max_score)
            
            # Generate details
            if screening_results['matched']:
                match_count = len(screening_results['matches'])
                highest_score = screening_results['risk_score']
                screening_results['details'] = f"Found {match_count} potential matches with highest similarity {highest_score:.2f}"
            else:
                screening_results['details'] = "No sanctions or PEP matches found"
            
            return screening_results
            
        except Exception as e:
            logger.error(f"Error in sanctions screening: {e}")
            return {
                'matched': False,
                'matches': [],
                'risk_score': 0.0,
                'details': f"Screening error: {str(e)}"
            }
    
    async def screen_against_sanctions(self, entity: Dict[str, Any], db: Session) -> List[Dict[str, Any]]:
        """Screen entity against sanctions lists"""
        try:
            entity_name = entity['name']
            matches = []
            
            # Get all sanctions list entries
            sanctions_entries = db.query(SanctionsList).all()
            
            for sanctions_entry in sanctions_entries:
                # Primary name match
                similarity = self.calculate_similarity(entity_name, sanctions_entry.entity_name)
                
                if similarity >= self.similarity_threshold:
                    matches.append({
                        'entity_type': 'SANCTIONS',
                        'list_name': sanctions_entry.list_name,
                        'matched_name': sanctions_entry.entity_name,
                        'similarity_score': similarity,
                        'match_type': 'PRIMARY_NAME',
                        'sanctions_program': sanctions_entry.program,
                        'entity_id': sanctions_entry.id
                    })
                
                # Check aliases
                if sanctions_entry.aliases:
                    for alias in sanctions_entry.aliases:
                        alias_similarity = self.calculate_similarity(entity_name, alias)
                        
                        if alias_similarity >= self.similarity_threshold:
                            matches.append({
                                'entity_type': 'SANCTIONS',
                                'list_name': sanctions_entry.list_name,
                                'matched_name': alias,
                                'similarity_score': alias_similarity,
                                'match_type': 'ALIAS',
                                'sanctions_program': sanctions_entry.program,
                                'entity_id': sanctions_entry.id
                            })
                
                # Additional screening for date of birth if available
                if (entity.get('date_of_birth') and sanctions_entry.date_of_birth and 
                    similarity >= 0.7):  # Lower threshold for name if DOB matches
                    
                    if self.compare_dates(entity['date_of_birth'], sanctions_entry.date_of_birth):
                        matches.append({
                            'entity_type': 'SANCTIONS',
                            'list_name': sanctions_entry.list_name,
                            'matched_name': sanctions_entry.entity_name,
                            'similarity_score': min(1.0, similarity + 0.2),  # Boost score for DOB match
                            'match_type': 'NAME_AND_DOB',
                            'sanctions_program': sanctions_entry.program,
                            'entity_id': sanctions_entry.id
                        })
            
            return matches
            
        except Exception as e:
            logger.error(f"Error screening against sanctions: {e}")
            return []
    
    async def screen_against_peps(self, entity: Dict[str, Any], db: Session) -> List[Dict[str, Any]]:
        """Screen entity against PEP lists"""
        try:
            entity_name = entity['name']
            matches = []
            
            # Get active PEP entries
            pep_entries = db.query(PEPList).filter(PEPList.is_active == True).all()
            
            for pep_entry in pep_entries:
                # Primary name match
                similarity = self.calculate_similarity(entity_name, pep_entry.full_name)
                
                if similarity >= self.similarity_threshold:
                    matches.append({
                        'entity_type': 'PEP',
                        'list_name': 'PEP_LIST',
                        'matched_name': pep_entry.full_name,
                        'similarity_score': similarity,
                        'match_type': 'PRIMARY_NAME',
                        'pep_position': pep_entry.position,
                        'pep_country': pep_entry.country,
                        'entity_id': pep_entry.id
                    })
                
                # Check aliases
                if pep_entry.aliases:
                    for alias in pep_entry.aliases:
                        alias_similarity = self.calculate_similarity(entity_name, alias)
                        
                        if alias_similarity >= self.similarity_threshold:
                            matches.append({
                                'entity_type': 'PEP',
                                'list_name': 'PEP_LIST',
                                'matched_name': alias,
                                'similarity_score': alias_similarity,
                                'match_type': 'ALIAS',
                                'pep_position': pep_entry.position,
                                'pep_country': pep_entry.country,
                                'entity_id': pep_entry.id
                            })
            
            return matches
            
        except Exception as e:
            logger.error(f"Error screening against PEPs: {e}")
            return []
    
    def calculate_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names using multiple techniques"""
        try:
            if not name1 or not name2:
                return 0.0
            
            # Normalize names
            norm_name1 = self.normalize_name(name1)
            norm_name2 = self.normalize_name(name2)
            
            # Exact match
            if norm_name1 == norm_name2:
                return 1.0
            
            # Token-based similarity
            token_similarity = self.calculate_token_similarity(norm_name1, norm_name2)
            
            # Sequence-based similarity
            sequence_similarity = SequenceMatcher(None, norm_name1, norm_name2).ratio()
            
            # Phonetic similarity
            phonetic_similarity = self.calculate_phonetic_similarity(norm_name1, norm_name2)
            
            # Weighted combination
            final_similarity = (
                token_similarity * 0.4 +
                sequence_similarity * 0.4 +
                phonetic_similarity * 0.2
            )
            
            return final_similarity
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        try:
            # Convert to uppercase
            normalized = name.upper().strip()
            
            # Remove special characters
            normalized = re.sub(r'[^\w\s]', ' ', normalized)
            
            # Replace multiple spaces with single space
            normalized = re.sub(r'\s+', ' ', normalized)
            
            # Apply name variations
            for full_form, abbreviations in self.name_variations.items():
                for abbrev in abbreviations:
                    normalized = re.sub(r'\b' + re.escape(abbrev) + r'\b', full_form, normalized)
            
            return normalized.strip()
            
        except Exception as e:
            logger.error(f"Error normalizing name: {e}")
            return name.upper()
    
    def calculate_token_similarity(self, name1: str, name2: str) -> float:
        """Calculate token-based similarity"""
        try:
            tokens1 = set(name1.split())
            tokens2 = set(name2.split())
            
            if not tokens1 or not tokens2:
                return 0.0
            
            # Jaccard similarity
            intersection = len(tokens1.intersection(tokens2))
            union = len(tokens1.union(tokens2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating token similarity: {e}")
            return 0.0
    
    def calculate_phonetic_similarity(self, name1: str, name2: str) -> float:
        """Calculate phonetic similarity using simple transliteration"""
        try:
            # Apply transliterations
            phonetic1 = name1
            phonetic2 = name2
            
            for original, replacement in self.transliterations.items():
                phonetic1 = phonetic1.replace(original, replacement)
                phonetic2 = phonetic2.replace(original, replacement)
            
            # Calculate similarity on phonetic versions
            return SequenceMatcher(None, phonetic1, phonetic2).ratio()
            
        except Exception as e:
            logger.error(f"Error calculating phonetic similarity: {e}")
            return 0.0
    
    def compare_dates(self, date1, date2) -> bool:
        """Compare dates allowing for minor variations"""
        try:
            if not date1 or not date2:
                return False
            
            # Convert to strings for comparison
            date1_str = str(date1) if hasattr(date1, 'strftime') else str(date1)
            date2_str = str(date2) if hasattr(date2, 'strftime') else str(date2)
            
            # Extract year from both dates
            year1 = re.search(r'\b(19|20)\d{2}\b', date1_str)
            year2 = re.search(r'\b(19|20)\d{2}\b', date2_str)
            
            if year1 and year2:
                return abs(int(year1.group()) - int(year2.group())) <= 1  # Allow 1 year difference
            
            return False
            
        except Exception as e:
            logger.error(f"Error comparing dates: {e}")
            return False
    
    async def update_sanctions_lists(self, db: Session) -> bool:
        """Update sanctions lists from external sources"""
        try:
            # In production, this would connect to OFAC, UN, EU APIs
            # For now, we'll create some sample entries
            
            sample_sanctions = [
                {
                    'list_name': 'OFAC_SDN',
                    'entity_name': 'BLOCKED PERSON ONE',
                    'entity_type': 'INDIVIDUAL',
                    'program': 'TERRORISM',
                    'aliases': ['BLOCKED ALIAS ONE', 'B.P. ONE']
                },
                {
                    'list_name': 'UN_SANCTIONS',
                    'entity_name': 'SANCTIONED COMPANY LTD',
                    'entity_type': 'ENTITY',
                    'program': 'PROLIFERATION',
                    'aliases': ['SANCTIONED CO', 'SANCTIONED CORP']
                }
            ]
            
            for entry in sample_sanctions:
                existing = db.query(SanctionsList).filter(
                    SanctionsList.entity_name == entry['entity_name']
                ).first()
                
                if not existing:
                    sanctions_entry = SanctionsList(**entry)
                    db.add(sanctions_entry)
            
            db.commit()
            logger.info("Sanctions lists updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating sanctions lists: {e}")
            db.rollback()
            return False
    
    async def update_pep_lists(self, db: Session) -> bool:
        """Update PEP lists from external sources"""
        try:
            # Sample PEP entries
            sample_peps = [
                {
                    'full_name': 'JOHN POLITICAL LEADER',
                    'position': 'MINISTER OF FINANCE',
                    'country': 'ZIMBABWE',
                    'category': 'MINISTER',
                    'is_active': True,
                    'aliases': ['J. POLITICAL LEADER', 'MINISTER JOHN']
                },
                {
                    'full_name': 'JANE HEAD OF STATE',
                    'position': 'PRESIDENT',
                    'country': 'SOUTH AFRICA',
                    'category': 'HEAD_OF_STATE',
                    'is_active': True,
                    'aliases': ['PRESIDENT JANE', 'J. HEAD OF STATE']
                }
            ]
            
            for entry in sample_peps:
                existing = db.query(PEPList).filter(
                    PEPList.full_name == entry['full_name']
                ).first()
                
                if not existing:
                    pep_entry = PEPList(**entry)
                    db.add(pep_entry)
            
            db.commit()
            logger.info("PEP lists updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating PEP lists: {e}")
            db.rollback()
            return False
