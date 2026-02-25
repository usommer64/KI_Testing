import pandas as pd
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class ProductMapper:
    def __init__(self, mapping_file: str = None):
        """
        Initialisiert den ProductMapper mit einer CSV-Mapping-Datei.
        
        Args:
            mapping_file: Pfad zur product_mapping.csv
        """
        if mapping_file is None:
            # Standard-Pfad relativ zum src/ Verzeichnis
            mapping_file = Path(__file__).parent.parent / "data" / "product_mapping.csv"
        
        self.mapping_file = Path(mapping_file)
        self.mapping_df = None
        self._load_mapping()
    
    def _load_mapping(self):
        """Lädt die Mapping-Datei."""
        try:
            if self.mapping_file.exists():
                self.mapping_df = pd.read_csv(self.mapping_file)
                logger.info(f"✅ Product Mapping geladen: {len(self.mapping_df)} Einträge")
            else:
                logger.warning(f"⚠️  Keine product_mapping.csv gefunden: {self.mapping_file}")
                self.mapping_df = pd.DataFrame(columns=['license_code', 'product_name', 'language', 'filename'])
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Mapping-Datei: {e}")
            self.mapping_df = pd.DataFrame(columns=['license_code', 'product_name', 'language', 'filename'])
    
    def get_product_info(self, filename: str) -> Optional[Dict[str, str]]:
        """
        Sucht Product Info anhand des Dateinamens.
        
        Args:
            filename: Name der Datei (z.B. "L-YRHY-YWPJ3V_de.pdf")
        
        Returns:
            Dict mit product_name, license_code, language oder None
        """
        if self.mapping_df is None or self.mapping_df.empty:
            return None
        
        # Exakte Suche nach Dateinamen
        match = self.mapping_df[self.mapping_df['filename'] == filename]
        
        if not match.empty:
            row = match.iloc[0]
            return {
                'product_name': row['product_name'],
                'license_code': row['license_code'],
                'language': row['language']
            }
        
        # Fallback: Suche nach License Code (ohne Sprache)
        license_code = filename.split('_')[0].replace('.pdf', '')
        match = self.mapping_df[self.mapping_df['license_code'] == license_code]
        
        if not match.empty:
            row = match.iloc[0]
            logger.info(f"📋 Fallback-Match für {filename} → {row['product_name']}")
            return {
                'product_name': row['product_name'],
                'license_code': row['license_code'],
                'language': row.get('language', 'unknown')
            }
        
        return None
    
    def add_mapping(self, license_code: str, product_name: str, language: str, filename: str):
        """Fügt ein neues Mapping hinzu."""
        new_row = pd.DataFrame([{
            'license_code': license_code,
            'product_name': product_name,
            'language': language,
            'filename': filename
        }])
        self.mapping_df = pd.concat([self.mapping_df, new_row], ignore_index=True)
    
    def save_mapping(self):
        """Speichert das Mapping zurück in die CSV."""
        try:
            self.mapping_df.to_csv(self.mapping_file, index=False)
            logger.info(f"💾 Product Mapping gespeichert: {self.mapping_file}")
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern: {e}")