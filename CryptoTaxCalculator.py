import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from collections import defaultdict

class CalculadoraFiscalProfesional:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculadora Fiscal Cripto Avanzada - Criterio FIFO Real")
        self.root.geometry("1000x700")
        self.root.configure(bg="#0f172a")
        
        # Estilos visuales de la interfaz
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TNotebook", background="#0f172a", borderwidth=0)
        self.style.configure("TNotebook.Tab", background="#1e293b", foreground="#94a3b8", font=("Segoe UI", 10), padding=[15, 5])
        self.style.map("TNotebook.Tab", background=[("selected", "#38bdf8")], foreground=[("selected", "#0f172a")])
        self.style.configure("Treeview", background="#1e293b", fieldbackground="#1e293b", foreground="#e2e8f0", borderwidth=0, font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", background="#1e293b", foreground="#38bdf8", font=("Segoe UI", 10, "bold"))

        self.create_widgets()
        
    def create_widgets(self):
        title_label = tk.Label(self.root, text="Consolidado Fiscal de Criptomonedas", font=("Segoe UI", 16, "bold"), bg="#0f172a", fg="#38bdf8")
        title_label.pack(pady=(20, 5))
        
        self.btn_buscar = tk.Button(self.root, text="📁 Seleccionar Historial .CSV de Binance", command=self.cargar_archivo, font=("Segoe UI", 10, "bold"), bg="#38bdf8", fg="#0f172a", activebackground="#0ea5e9", padx=20, pady=8, bd=0, cursor="hand2")
        self.btn_buscar.pack(pady=10)

        self.lbl_archivo = tk.Label(self.root, text="Ningún archivo seleccionado", font=("Segoe UI", 9, "italic"), bg="#0f172a", fg="#64748b")
        self.lbl_archivo.pack(pady=(0, 10))

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=30, pady=10)
        
        self.frame_vacio = tk.Frame(self.notebook, bg="#1e293b")
        self.notebook.add(self.frame_vacio, text="Resultados")
        lbl_vacio = tk.Label(self.frame_vacio, text="Por favor, carga tu archivo CSV para generar las pestañas por años.", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 11))
        lbl_vacio.pack(pady=100)

    def cargar_archivo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Archivos CSV", "*.csv")])
        if not file_path:
            return
            
        self.lbl_archivo.config(text=f"Archivo activo: {os.path.basename(file_path)}")
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
            
        try:
            self.procesar_fiscalidad(file_path)
        except Exception as e:
            messagebox.showerror("Error de Procesamiento", f"Error analizando el FIFO:\n{str(e)}")

    def procesar_fiscalidad(self, path):
        df = pd.read_csv(path)
        df['Time'] = pd.to_datetime(df['Time'])
        
        # Ventana de 15 segundos para agrupar las dos patas de cada conversión de Binance
        df['Time_Group'] = df['Time'].dt.round('15s')
        df = df.sort_values('Time').reset_index(drop=True)

        bloques = defaultdict(list)
        for _, row in df.iterrows():
            bloques[row['Time_Group']].append(row)

        # Estructura FIFO: inventario[TOKEN] = [{'cantidad': X, 'coste_total_eur': Y}]
        inventario = defaultdict(list)
        reporte = defaultdict(lambda: defaultdict(lambda: {"ganancias": 0.0, "perdidas": 0.0}))
        
        stablecoins = {'USDT', 'USDC', 'BUSD', 'FDUSD'}

        for timestamp, filas in sorted(bloques.items()):
            year = str(timestamp.year)
            
            compras = [f for f in filas if f['Change'] > 0 and f['Operation'] not in ['Deposit', 'Simple Earn Flexible Interest', 'Simple Earn Locked Rewards', 'Simple Earn Locked Redemption', 'Simple Earn Flexible Redemption']]
            ventas = [f for f in filas if f['Change'] < 0 and f['Operation'] not in ['Withdraw', 'Simple Earn Flexible Subscription', 'Simple Earn Locked Subscription']]
            staking = [f for f in filas if f['Operation'] in ['Simple Earn Flexible Interest', 'Simple Earn Locked Rewards']]

            # 1. Tratar ingresos por Staking (coste adquisición = 0€)
            for st in staking:
                coin = st['Coin']
                cant = float(st['Change'])
                if cant > 0 and coin != 'EUR':
                    inventario[coin].append({'cantidad': cant, 'coste_total_eur': 0.0})

            # 2. Buscar si hay rastro Fiat real explícito en este bloque (Euros o Stables)
            fiat_directo_eur = 0.0
            for f in filas:
                if f['Coin'] == 'EUR':
                    fiat_directo_eur = abs(float(f['Change']))
                    break
            if fiat_directo_eur == 0.0:
                for f in filas:
                    if f['Coin'] in stablecoins:
                        fiat_directo_eur = abs(float(f['Change']))
                        break

            # 3. CASO PERMUTA CRIPTO-CRIPTO (Ej: Vender BTC para comprar PEPE o viceversa)
            if compras and ventas:
                coste_fifo_salida_eur = 0.0
                hubo_fiat = (fiat_directo_eur > 0.0)
                
                # Liquidamos la cripto que se vende y vemos cuánto nos costó en su día
                for v in ventas:
                    token_venta = v['Coin']
                    cant_venta = abs(float(v['Change']))
                    if token_venta == 'EUR':
                        coste_fifo_salida_eur += cant_venta
                        continue
                        
                    cant_por_vender = cant_venta
                    while cant_por_vender > 0.00000001 and inventario[token_venta]:
                        lote = inventario[token_venta][0]
                        cant_lote_vencido = min(cant_por_vender, lote['cantidad'])
                        
                        # Calculamos la parte proporcional del coste real en euros que compramos en el pasado
                        proporcion_coste_eur = (cant_lote_vencido / lote['cantidad']) * lote['coste_total_eur']
                        coste_fifo_salida_eur += proporcion_coste_eur
                        
                        # Si hay salida directa a Fiat/Euros en la transacción, calculamos ganancia inmediatamente
                        if hubo_fiat:
                            precio_unitario_venta = fiat_directo_eur / cant_venta
                            valor_venta_lote_eur = cant_lote_vencido * precio_unitario_venta
                            rendimiento = valor_venta_lote_eur - proporcion_coste_eur
                            if rendimiento >= 0:
                                reporte[year][token_venta]["ganancias"] += rendimiento
                            else:
                                reporte[year][token_venta]["perdidas"] += abs(rendimiento)
                        
                        # Actualizar lote
                        cant_por_vender -= cant_lote_vencido
                        lote['cantidad'] -= cant_lote_vencido
                        lote['coste_total_eur'] -= proporcion_coste_eur
                        if lote['cantidad'] <= 0.00000001:
                            inventario[token_venta].pop(0)

                # La cripto que entra (compra) hereda estrictamente el coste acumulado en Euros de la que salió
                coste_para_las_compras = fiat_directo_eur if hubo_fiat else coste_fifo_salida_eur
                
                for c in compras:
                    token_compra = c['Coin']
                    cant_compra = float(c['Change'])
                    if token_compra == 'EUR': continue
                    
                    # Guardamos el lote de la nueva moneda con su coste real en euros arrastrado
                    coste_asignado = coste_para_las_compras / len(compras)
                    inventario[token_compra].append({'cantidad': cant_compra, 'coste_total_eur': coste_asignado})

            # 4. COMPRAS ASILADAS CON FIAT (Ej: Tus primeras operaciones de 2023)
            elif compras:
                for c in compras:
                    token_compra = c['Coin']
                    cant_compra = float(c['Change'])
                    if token_compra == 'EUR': continue
                    
                    # Si no hay valor fiat en el bloque pero es una stablecoin, su coste es su cantidad (1:1)
                    coste_eur = fiat_directo_eur if fiat_directo_eur > 0.0 else (cant_compra if token_compra in stablecoins else 0.0)
                    inventario[token_compra].append({'cantidad': cant_compra, 'coste_total_eur': coste_eur})

            # 5. VENTAS AISLADAS
            elif ventas:
                for v in ventas:
                    token_venta = v['Coin']
                    cant_venta = abs(float(v['Change']))
                    if token_venta == 'EUR': continue
                    
                    valor_venta_eur = fiat_directo_eur if fiat_directo_eur > 0.0 else (cant_venta if token_venta in stablecoins else 0.0)
                    precio_venta_unitario = valor_venta_eur / cant_venta if cant_venta > 0 else 0.0
                    
                    cant_por_vender = cant_venta
                    while cant_por_vender > 0.00000001 and inventario[token_venta]:
                        lote = inventario[token_venta][0]
                        cant_lote_vencido = min(cant_por_vender, lote['cantidad'])
                        
                        proporcion_coste_eur = (cant_lote_vencido / lote['cantidad']) * lote['coste_total_eur']
                        valor_venta_lote_eur = cant_lote_vencido * precio_venta_unitario
                        
                        rendimiento = valor_venta_lote_eur - proporcion_coste_eur
                        if rendimiento >= 0:
                            reporte[year][token_venta]["ganancias"] += rendimiento
                        else:
                            reporte[year][token_venta]["perdidas"] += abs(rendimiento)
                            
                        cant_por_vender -= cant_lote_vencido
                        lote['cantidad'] -= cant_lote_vencido
                        lote['coste_total_eur'] -= proporcion_coste_eur
                        if lote['cantidad'] <= 0.00000001:
                            inventario[token_venta].pop(0)

        # DIBUJAR PESTAÑAS (INCLUYENDO 2023)
        # Nos aseguramos de que aparezcan todos los años fiscales de los datos
        anos_encontrados = sorted(list(set([str(d.year) for d in df['Time']])))
        
        for year in anos_encontrados:
            tab_frame = tk.Frame(self.notebook, bg="#0f172a")
            self.notebook.add(tab_frame, text=f" Año {year} ")
            
            tabla_container = tk.Frame(tab_frame, bg="#0f172a")
            tabla_container.pack(fill="both", expand=True, padx=20, pady=20)
            
            scrollbar = ttk.Scrollbar(tabla_container)
            scrollbar.pack(side="right", fill="y")
            
            tree = ttk.Treeview(tabla_container, columns=("Token", "Ganancias", "Pérdidas", "Neto"), show="headings", yscrollcommand=scrollbar.set, height=15)
            tree.heading("Token", text="CRIPTO")
            tree.heading("Ganancias", text="GANANCIAS (+)")
            tree.heading("Pérdidas", text="PÉRDIDAS (-)")
            tree.heading("Neto", text="RENDIMIENTO NETO")
            
            tree.column("Token", anchor="center", width=150)
            tree.column("Ganancias", anchor="e", width=200)
            tree.column("Pérdidas", anchor="e", width=200)
            tree.column("Neto", anchor="e", width=220)
            
            tree.pack(fill="both", expand=True)
            scrollbar.config(command=tree.yview)
            
            total_neto_ano = 0.0
            if year in reporte:
                for token in sorted(reporte[year].keys()):
                    gan = reporte[year][token]["ganancias"]
                    per = reporte[year][token]["perdidas"]
                    neto = gan - per
                    
                    if gan == 0.0 and per == 0.0:
                        continue
                        
                    total_neto_ano += neto
                    tree.insert("", tk.END, values=(
                        token, 
                        f"{gan:,.2f} €", 
                        f"{per:,.2f} €", 
                        f"{neto:,.2f} €"
                    ))
            
            color_resumen = "#4ade80" if total_neto_ano >= 0 else "#f87171"
            lbl_resumen = tk.Label(tab_frame, text=f"Resultado Total Neto del Año {year}: {total_neto_ano:,.2f} €", font=("Segoe UI", 11, "bold"), bg="#1e293b", fg=color_resumen, pady=10)
            lbl_resumen.pack(fill="x", side="bottom")

if __name__ == "__main__":
    root = tk.Tk()
    app = CalculadoraFiscalProfesional(root)
    root.mainloop()