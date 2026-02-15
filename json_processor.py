import json
import pandas as pd
import re

class JSONProcessor:
    def __init__(self):
        self.data_list = []
        self.df = None

    def add_json(self, content, filename):
        try:
            if isinstance(content, bytes):
                try:
                    content_str = content.decode('utf-8')
                except UnicodeDecodeError:
                    content_str = content.decode('latin-1', errors='replace')
            else:
                content_str = content

            json_data = json.loads(content_str)
            extracted_data = self._extract_dte_data(json_data, filename)
            
            if isinstance(extracted_data, list):
                self.data_list.extend(extracted_data)
            elif extracted_data:
                self.data_list.append(extracted_data)
                
        except json.JSONDecodeError as e:
            print(f"Error de formato JSON en {filename}: {str(e)}")
        except Exception as e:
            print(f"Error procesando {filename}: {str(e)}")

    def _safe_get(self, dictionary, *keys):
        if not isinstance(dictionary, dict):
            return None
            
        for key in keys:
            if key in dictionary:
                return dictionary[key]
            key_title = key.title()
            if key_title in dictionary:
                return dictionary[key_title]
            key_lower = key[0].lower() + key[1:] if len(key) > 1 else key.lower()
            if key_lower in dictionary:
                return dictionary[key_lower]
        return None

    def _extract_dte_data(self, data, filename):
        if not isinstance(data, dict):
            return None
            
        identificacion = data.get('identificacion', {})
        tipo_dte = self._safe_get(identificacion, 'TipoDte', 'tipoDte') or ''
        
        emisor = data.get('emisor', {})
        emisor_nit = self._safe_get(emisor, 'Nit', 'nit') or ''
        emisor_nrc = self._safe_get(emisor, 'Nrc', 'nrc') or ''
        emisor_nombre = self._safe_get(emisor, 'Nombre', 'nombre') or ''
        emisor_comercial = self._safe_get(emisor, 'NombreComercial', 'nombreComercial') or ''
        
        receptor = data.get('receptor', {})
        receptor_nit = self._safe_get(receptor, 'nit', 'Nit', 'numDocumento') or ''
        receptor_nrc = self._safe_get(receptor, 'nrc', 'Nrc') or ''
        receptor_nombre = self._safe_get(receptor, 'nombre', 'Nombre') or ''
        
        resumen = data.get('resumen', {})
        total_pagar = self._safe_get(resumen, 'TotalPagar', 'totalPagar') or 0
        total_gravada = self._safe_get(resumen, 'TotalGravada', 'totalGravada') or 0
        total_iva = self._safe_get(resumen, 'TotalIva', 'totalIva') or 0
        
        base_info = {
            'archivo_origen': filename,
            'tipo_dte': tipo_dte,
            'codigo_generacion': self._safe_get(identificacion, 'CodigoGeneracion', 'codigoGeneracion') or '',
            'numero_control': self._safe_get(identificacion, 'NumeroControl', 'numeroControl') or '',
            'fecha_emision': self._safe_get(identificacion, 'FecEmi', 'fecEmi') or '',
            'hora_emision': self._safe_get(identificacion, 'HorEmi', 'horEmi') or '',
            'emisor_nit': emisor_nit,
            'emisor_nrc': emisor_nrc,
            'emisor_nombre': emisor_nombre,
            'emisor_nombre_comercial': emisor_comercial,
            'receptor_nit': receptor_nit,
            'receptor_nrc': receptor_nrc,
            'receptor_nombre': receptor_nombre,
            'total_gravada': total_gravada,
            'total_iva': total_iva,
            'total_pagar': total_pagar
        }
        
        cuerpo = data.get('cuerpoDocumento', [])
        if cuerpo and isinstance(cuerpo, list):
            items_data = []
            for item in cuerpo:
                if not isinstance(item, dict):
                    continue
                new_row = base_info.copy()
                new_row.update({
                    'item_num': self._safe_get(item, 'numItem', 'NumItem') or 0,
                    'item_codigo': self._safe_get(item, 'codigo', 'Codigo') or '',
                    'item_cantidad': self._safe_get(item, 'cantidad', 'Cantidad') or 0,
                    'item_descripcion': self._safe_get(item, 'descripcion', 'Descripcion') or '',
                    'item_precio_unitario': self._safe_get(item, 'precioUni', 'PrecioUni') or 0,
                    'item_monto_descuento': self._safe_get(item, 'montoDescu', 'MontoDescu') or 0,
                    'item_venta_gravada': self._safe_get(item, 'ventaGravada', 'VentaGravada') or 0,
                    'item_iva': self._safe_get(item, 'ivaItem', 'IvaItem') or 0
                })
                items_data.append(new_row)
            return items_data
        
        return base_info

    def export_to_excel(self, output_path):
        if not self.data_list:
            raise Exception("La lista de datos está vacía. Ningún JSON fue procesado correctamente.")
            
        self.df = pd.DataFrame(self.data_list)
        
        column_mapping = {
            'codigo_generacion': 'codigoGeneracion',
            'fecha_emision': 'fechaEmision',
            'total_pagar': 'totalPagar'
        }
        
        self.df.rename(columns=column_mapping, inplace=True)
        
        # LIMPIEZA CRÍTICA: Eliminar caracteres de control invisibles que rompen openpyxl
        self.df = self.df.replace(r'[\x00-\x1F\x7F-\x9F]', '', regex=True)
        
        priority_cols = ['archivo_origen', 'tipo_dte', 'fechaEmision', 'numero_control',
                        'emisor_nombre', 'emisor_nit', 'receptor_nombre', 'receptor_nit',
                        'item_descripcion', 'item_cantidad', 'item_precio_unitario', 
                        'item_venta_gravada', 'totalPagar']
        
        existing_priority = [c for c in priority_cols if c in self.df.columns]
        other_cols = [c for c in self.df.columns if c not in existing_priority]
        self.df = self.df[existing_priority + other_cols]
        
        try:
            self.df.to_excel(output_path, index=False, engine='openpyxl')
        except ImportError:
            raise Exception("Falta la librería openpyxl. Instálala con: pip install openpyxl")
            
        return output_path