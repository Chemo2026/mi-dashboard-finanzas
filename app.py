import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Finanzas Personales", page_icon="💰", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Falta configurar la conexión a Google Sheets. Sigue las instrucciones para agregar los 'Secrets'.")
    st.stop()

def load_data():
    try:
        # Leemos las primeras 5 columnas
        df = conn.read(usecols=list(range(5)), ttl=0) 
        df = df.dropna(how='all') # Eliminar filas completamente vacías
        
        if df.empty:
            return pd.DataFrame(columns=['Tipo', 'Categoría', 'Monto', 'Fecha', 'Descripción'])
            
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        return df
    except Exception as e:
        st.error(f"Error al leer de Google Sheets: {e}")
        return pd.DataFrame(columns=['Tipo', 'Categoría', 'Monto', 'Fecha', 'Descripción'])

def save_data(df):
    df_to_save = df.copy()
    # Asegurarnos de que sea formato fecha antes de convertirlo a texto
    df_to_save['Fecha'] = pd.to_datetime(df_to_save['Fecha'])
    df_to_save['Fecha'] = df_to_save['Fecha'].dt.strftime('%Y-%m-%d')
    conn.update(data=df_to_save)

df = load_data()

# --- BARRA LATERAL (INGRESO DE DATOS) ---
st.sidebar.header("Registrar Nuevo Movimiento")

tipo = st.sidebar.selectbox("Tipo", ["Ingreso", "Gasto"])

if tipo == "Ingreso":
    categorias = ["Sueldo", "Trabajos extra", "Otros"]
else:
    categorias = [
        "Vivienda", "Servicios", "Suscripciones", "Educación", "Transporte", 
        "Alimentación (Mercado)", "Comida fuera (Snacks/Restaurantes)", 
        "Salud", "Entretenimiento", "Ropa/Cuidado personal"
    ]

categoria = st.sidebar.selectbox("Categoría", categorias)
monto = st.sidebar.number_input("Monto", min_value=0.01, format="%.2f")
fecha = st.sidebar.date_input("Fecha", datetime.today())
descripcion = st.sidebar.text_input("Descripción (Ej. Pasaje a la universidad)")

if st.sidebar.button("Guardar registro"):
    nuevo_registro = pd.DataFrame([{
        'Tipo': tipo,
        'Categoría': categoria,
        'Monto': monto,
        'Fecha': pd.to_datetime(fecha),
        'Descripción': descripcion
    }])
    df = pd.concat([df, nuevo_registro], ignore_index=True)
    save_data(df)
    st.sidebar.success("¡Registro guardado con éxito en Google Sheets!")
    # Recargar los datos inmediatamente
    df = load_data()

# --- PANEL PRINCIPAL ---
st.title("💰 Dashboard de Finanzas Personales")

# Filtros por Mes y Año
current_month = datetime.now().month
current_year = datetime.now().year

col1, col2 = st.columns(2)
with col1:
    nombres_meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_seleccionado = st.selectbox(
        "Mes", 
        options=list(range(1, 13)), 
        format_func=lambda x: nombres_meses[x-1], 
        index=current_month-1
    )
with col2:
    if not df.empty and df['Fecha'].notna().any():
        years_disponibles = sorted(list(set(df['Fecha'].dt.year.dropna().astype(int).tolist() + [current_year])), reverse=True)
    else:
        years_disponibles = [current_year]
    year_seleccionado = st.selectbox("Año", years_disponibles)

# Filtrar datos por mes y año
df_filtrado = df[(df['Fecha'].dt.month == mes_seleccionado) & (df['Fecha'].dt.year == year_seleccionado)]

# --- KPIs ---
ingresos_totales = df_filtrado[df_filtrado['Tipo'] == 'Ingreso']['Monto'].sum()
gastos_totales = df_filtrado[df_filtrado['Tipo'] == 'Gasto']['Monto'].sum()
saldo = ingresos_totales - gastos_totales

st.markdown("---")
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric(label="Ingresos Totales", value=f"${ingresos_totales:,.2f}")
kpi2.metric(label="Gastos Totales", value=f"${gastos_totales:,.2f}")
kpi3.metric(label="Saldo Disponible", value=f"${saldo:,.2f}")
st.markdown("---")

if not df_filtrado.empty:
    # --- GRÁFICOS (PLOTLY) ---
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Gráfico de Pastel: Distribución de Gastos por Categoría
        df_gastos = df_filtrado[df_filtrado['Tipo'] == 'Gasto']
        if not df_gastos.empty:
            gastos_por_categoria = df_gastos.groupby('Categoría')['Monto'].sum().reset_index()
            fig_pie = px.pie(
                gastos_por_categoria, 
                values='Monto', 
                names='Categoría', 
                title='Distribución de Gastos por Categoría', 
                hole=0.3
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos registrados en este mes para mostrar el gráfico de distribución.")
            
    with col_chart2:
        # Gráfico de Barras: Ingresos vs Gastos
        df_resumen = pd.DataFrame({
            'Tipo': ['Ingreso', 'Gasto'],
            'Monto': [ingresos_totales, gastos_totales]
        })
        fig_bar = px.bar(
            df_resumen, 
            x='Tipo', 
            y='Monto', 
            color='Tipo', 
            title='Comparación: Ingresos vs Gastos', 
            color_discrete_map={'Ingreso':'green', 'Gasto':'red'}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Gráfico de Líneas: Tendencia de gastos diarios
    st.subheader("Tendencia de Gastos Diarios")
    if not df_gastos.empty:
        gastos_diarios = df_gastos.groupby(df_gastos['Fecha'].dt.date)['Monto'].sum().reset_index()
        fig_line = px.line(
            gastos_diarios, 
            x='Fecha', 
            y='Monto', 
            title='Gastos a lo largo del mes', 
            markers=True
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No hay gastos registrados para mostrar la tendencia diaria.")

# --- TABLA DE DATOS ---
st.markdown("---")
st.subheader("Últimos Registros")
if not df.empty:
    st.dataframe(df.sort_values(by='Fecha', ascending=False), use_container_width=True)
else:
    st.info("Aún no hay registros. ¡Usa la barra lateral para agregar uno nuevo!")
