"""
============================================================
  ASERRIO MONITOR - Dashboard Streamlit + InfluxDB Cloud
============================================================
  pip install streamlit influxdb-client plotly pandas
  streamlit run aserrio_dashboard.py
============================================================
"""

import streamlit as st
from influxdb_client import InfluxDBClient
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import time

# ── Página ────────────────────────────────────────────────
st.set_page_config(
    page_title="Aserrio Monitor",
    page_icon="🪵",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
  .stApp { background-color: #0a0d0f; }
  section[data-testid="stSidebar"] { background-color: #111518; }
  .kpi { background:#111518; border:1px solid #1e2830; border-radius:10px;
         padding:18px; text-align:center; border-top:3px solid #00e5a0; }
  .kpi.blue   { border-top-color:#00b8ff; }
  .kpi.warn   { border-top-color:#ff9500; }
  .kpi.purple { border-top-color:#9c6ee8; }
  .kpi.red    { border-top-color:#ff3a3a; }
  .kpi-label  { font-size:10px; letter-spacing:2px; color:#4a6070;
                text-transform:uppercase; font-family:monospace; margin-bottom:6px; }
  .kpi-val    { font-size:36px; font-weight:700; color:#00e5a0; line-height:1; }
  .kpi-val.blue   { color:#00b8ff; }
  .kpi-val.white  { color:#fff; }
  .kpi-val.warn   { color:#ff9500; }
  .kpi-val.purple { color:#9c6ee8; }
  .kpi-val.red    { color:#ff3a3a; }
  .kpi-unit   { font-size:11px; color:#4a6070; margin-top:3px; font-family:monospace; }
  .alerta     { background:rgba(255,58,58,0.1); border:1px solid #ff3a3a;
                border-radius:8px; padding:10px 14px; color:#ff3a3a;
                font-family:monospace; font-size:13px; margin-bottom:6px; }
  .alerta.warn{ border-color:#ff9500; color:#ff9500; background:rgba(255,149,0,0.1); }
  #MainMenu,footer,header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar / Config ──────────────────────────────────────
with st.sidebar:
    st.markdown("### 🗄 InfluxDB Cloud")
    influx_url    = st.text_input("URL", value="https://us-east-1-1.aws.cloud2.influxdata.com")
    influx_token  = st.text_input("Token", type="password",
                                   value="GwHOA55GemA6wvAdcW3mPpR83QKMeHMCNArUCVpHlkMm-8Hb5LhwoXWGWoedGHyDG2M2BLSvsUCIJH9oCWFlsg==")
    influx_org    = st.text_input("Organización", value="Aserrio Ganges")
    influx_bucket = st.text_input("Bucket", value="Monitor_Coche_Horizontal")

    st.markdown("---")
    st.markdown("### ⚙️ Dashboard")
    refresh      = st.slider("Actualizar cada (s)", 2, 30, 5)
    rango_tiempo = st.selectbox("Rango de tiempo",
                                ["-1h", "-3h", "-6h", "-12h", "-24h", "-7d"],
                                index=0)
    umbral_A     = st.number_input("Alerta corriente (A)", value=80, step=5)
    umbral_desb  = st.number_input("Alerta desbalance (%)", value=15, step=1)

    st.markdown("---")
    st.markdown("""<div style='font-family:monospace;font-size:10px;color:#4a6070'>
    ASERRIO MONITOR v3.0<br>ESP32 + InfluxDB Cloud<br>EAFIT 2024</div>""",
                unsafe_allow_html=True)

# ── Cliente InfluxDB ──────────────────────────────────────
@st.cache_resource
def get_client(url, token, org):
    return InfluxDBClient(url=url, token=token, org=org)

def query(client, org, flux):
    try:
        tables = client.query_api().query(flux, org=org)
        rows = []
        for table in tables:
            for record in table.records:
                rows.append({"time": record.get_time(), "field": record.get_field(),
                             "value": record.get_value(), "measurement": record.get_measurement()})
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame()

def fmt_tiempo(ms):
    if not ms or ms <= 0: return "0:00"
    s = int(ms / 1000); m = s // 60; h = m // 60
    return f"{h}:{m%60:02d}:{s%60:02d}" if h > 0 else f"{m}:{s%60:02d}"

# ── Header ────────────────────────────────────────────────
col_h, col_s = st.columns([4, 1])
with col_h:
    st.markdown("""
    <div style='font-size:30px;font-weight:700;letter-spacing:4px;color:#fff'>
      🪵 ASERRIO<span style='color:#00e5a0'>MON</span>
    </div>
    <div style='font-size:10px;letter-spacing:3px;color:#4a6070;font-family:monospace'>
      MONITOR EN TIEMPO REAL — ASERRÍO GANGES — COCHE HORIZONTAL
    </div>
    """, unsafe_allow_html=True)

status_ph = col_s.empty()
main_ph   = st.empty()

# ── Loop ─────────────────────────────────────────────────
while True:
    try:
        client = get_client(influx_url, influx_token, influx_org)

        # ── Queries ───────────────────────────────────────
        # Último valor de corrientes
        q_curr = f'''
        from(bucket: "{influx_bucket}")
          |> range(start: -1m)
          |> filter(fn: (r) => r._measurement == "corriente")
          |> last()
        '''

        # Troncos en el rango seleccionado
        q_troncos = f'''
        from(bucket: "{influx_bucket}")
          |> range(start: {rango_tiempo})
          |> filter(fn: (r) => r._measurement == "tronco")
          |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")
        '''

        # Corrientes históricas para graficar
        q_curr_hist = f'''
        from(bucket: "{influx_bucket}")
          |> range(start: {rango_tiempo})
          |> filter(fn: (r) => r._measurement == "corriente")
          |> filter(fn: (r) => r._field == "L1_A" or r._field == "L2_A" or r._field == "L3_A" or r._field == "total_kW")
          |> aggregateWindow(every: 1m, fn: mean, createEmpty: false)
        '''

        df_curr      = query(client, influx_org, q_curr)
        df_troncos   = query(client, influx_org, q_troncos)
        df_curr_hist = query(client, influx_org, q_curr_hist)

        # Extraer últimas corrientes
        def last_val(df, field, default=0.0):
            if df.empty: return default
            sub = df[df["field"] == field]
            return float(sub["value"].iloc[-1]) if not sub.empty else default

        l1  = last_val(df_curr, "L1_A")
        l2  = last_val(df_curr, "L2_A")
        l3  = last_val(df_curr, "L3_A")
        kw  = last_val(df_curr, "total_kW")
        dsb = last_val(df_curr, "desbalance")

        # Stats troncos
        if not df_troncos.empty and "longitud_cm" in df_troncos.columns:
            df_t       = df_troncos.sort_values("time")
            total_t    = len(df_t)
            prod_cm    = df_t["longitud_cm"].sum() if "longitud_cm" in df_t else 0
            avg_len    = df_t["longitud_cm"].mean() if "longitud_cm" in df_t else 0
            max_len    = df_t["longitud_cm"].max()  if "longitud_cm" in df_t else 0
            min_len    = df_t["longitud_cm"].min()  if "longitud_cm" in df_t else 0
        else:
            total_t = 0; prod_cm = 0; avg_len = 0; max_len = 0; min_len = 0

        online = not df_curr.empty or not df_troncos.empty

        status_ph.markdown(
            f"<div style='font-family:monospace;font-size:12px;color:{'#00e5a0' if online else '#ff3a3a'};text-align:right'>"
            f"{'● EN LÍNEA' if online else '● SIN DATOS'}<br>{datetime.now().strftime('%H:%M:%S')}</div>",
            unsafe_allow_html=True)

        with main_ph.container():

            # ── Alertas ───────────────────────────────────
            if l1 > umbral_A:
                st.markdown(f"<div class='alerta'>⚡ L1 supera límite: {l1:.1f}A (máx {umbral_A}A)</div>", unsafe_allow_html=True)
            if l2 > umbral_A:
                st.markdown(f"<div class='alerta'>⚡ L2 supera límite: {l2:.1f}A (máx {umbral_A}A)</div>", unsafe_allow_html=True)
            if l3 > umbral_A:
                st.markdown(f"<div class='alerta'>⚡ L3 supera límite: {l3:.1f}A (máx {umbral_A}A)</div>", unsafe_allow_html=True)
            if dsb > umbral_desb:
                st.markdown(f"<div class='alerta warn'>⚠️ Desbalance trifásico: {dsb:.1f}% (máx {umbral_desb}%)</div>", unsafe_allow_html=True)

            # ── KPIs producción ───────────────────────────
            st.markdown("#### 📊 Producción")
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.markdown(f"<div class='kpi'><div class='kpi-label'>Troncos</div><div class='kpi-val'>{total_t}</div><div class='kpi-unit'>en {rango_tiempo}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='kpi blue'><div class='kpi-label'>Producción</div><div class='kpi-val blue'>{prod_cm/100:.1f}</div><div class='kpi-unit'>metros lineales</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='kpi warn'><div class='kpi-label'>Largo promedio</div><div class='kpi-val warn'>{avg_len:.0f}</div><div class='kpi-unit'>cm por tronco</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='kpi purple'><div class='kpi-label'>Máximo</div><div class='kpi-val purple'>{max_len:.0f}</div><div class='kpi-unit'>cm</div></div>", unsafe_allow_html=True)
            c5.markdown(f"<div class='kpi'><div class='kpi-label'>Mínimo</div><div class='kpi-val white'>{min_len:.0f}</div><div class='kpi-unit'>cm</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── KPIs eléctricos ───────────────────────────
            st.markdown("#### ⚡ Monitoreo Trifásico")
            e1,e2,e3,e4,e5 = st.columns(5)
            cl1 = "red" if l1>umbral_A else "white"
            cl2 = "red" if l2>umbral_A else "white"
            cl3 = "red" if l3>umbral_A else "white"
            cdb = "red" if dsb>umbral_desb else "warn"
            e1.markdown(f"<div class='kpi {'red' if l1>umbral_A else ''}'><div class='kpi-label'>Fase L1</div><div class='kpi-val {cl1}'>{l1:.1f}</div><div class='kpi-unit'>Amperios RMS</div></div>", unsafe_allow_html=True)
            e2.markdown(f"<div class='kpi {'red' if l2>umbral_A else ''}'><div class='kpi-label'>Fase L2</div><div class='kpi-val {cl2}'>{l2:.1f}</div><div class='kpi-unit'>Amperios RMS</div></div>", unsafe_allow_html=True)
            e3.markdown(f"<div class='kpi {'red' if l3>umbral_A else ''}'><div class='kpi-label'>Fase L3</div><div class='kpi-val {cl3}'>{l3:.1f}</div><div class='kpi-unit'>Amperios RMS</div></div>", unsafe_allow_html=True)
            e4.markdown(f"<div class='kpi blue'><div class='kpi-label'>Potencia Total</div><div class='kpi-val blue'>{kw:.2f}</div><div class='kpi-unit'>kW</div></div>", unsafe_allow_html=True)
            e5.markdown(f"<div class='kpi {'red' if dsb>umbral_desb else 'warn'}'><div class='kpi-label'>Desbalance</div><div class='kpi-val {cdb}'>{dsb:.1f}%</div><div class='kpi-unit'>entre fases</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Gráficos ──────────────────────────────────
            g1, g2 = st.columns(2)

            with g1:
                st.markdown("##### Longitud de troncos")
                if not df_troncos.empty and "longitud_cm" in df_troncos.columns:
                    df_plot = df_t.tail(40).copy()
                    avg_v   = df_plot["longitud_cm"].mean()
                    colors  = ["#00b8ff" if v > avg_v*1.1 else "#ff9500" if v < avg_v*0.9 else "#00e5a0"
                               for v in df_plot["longitud_cm"]]
                    fig = go.Figure()
                    fig.add_bar(x=list(range(1, len(df_plot)+1)),
                                y=df_plot["longitud_cm"], marker_color=colors)
                    fig.add_hline(y=avg_v, line_dash="dash", line_color="#fff",
                                  opacity=0.4, annotation_text=f"Prom {avg_v:.0f}cm")
                    fig.update_layout(paper_bgcolor="#111518", plot_bgcolor="#0a0d0f",
                                      font_color="#c8d6df", height=260,
                                      margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
                                      xaxis=dict(gridcolor="#1e2830"),
                                      yaxis=dict(gridcolor="#1e2830", title="cm"))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Sin datos de troncos aún")

            with g2:
                st.markdown("##### Corriente trifásica histórica")
                if not df_curr_hist.empty:
                    fig2 = go.Figure()
                    colores = {"L1_A":"#00e5a0", "L2_A":"#00b8ff", "L3_A":"#ff9500"}
                    for fase, color in colores.items():
                        sub = df_curr_hist[df_curr_hist["field"] == fase]
                        if not sub.empty:
                            fig2.add_scatter(x=sub["time"], y=sub["value"],
                                             name=fase.replace("_A",""),
                                             line=dict(color=color, width=2))
                    fig2.add_hline(y=umbral_A, line_dash="dash", line_color="#ff3a3a",
                                   opacity=0.6, annotation_text=f"Límite {umbral_A}A")
                    fig2.update_layout(paper_bgcolor="#111518", plot_bgcolor="#0a0d0f",
                                       font_color="#c8d6df", height=260,
                                       margin=dict(l=0,r=0,t=10,b=0),
                                       legend=dict(font=dict(color="#c8d6df")),
                                       xaxis=dict(gridcolor="#1e2830"),
                                       yaxis=dict(gridcolor="#1e2830", title="A"))
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("Sin historial de corrientes aún")

            # ── Potencia histórica ─────────────────────────
            st.markdown("##### Potencia consumida (kW)")
            if not df_curr_hist.empty:
                sub_kw = df_curr_hist[df_curr_hist["field"] == "total_kW"]
                if not sub_kw.empty:
                    fig3 = go.Figure()
                    fig3.add_scatter(x=sub_kw["time"], y=sub_kw["value"],
                                     fill="tozeroy", line=dict(color="#9c6ee8", width=2),
                                     fillcolor="rgba(156,110,232,0.15)")
                    fig3.update_layout(paper_bgcolor="#111518", plot_bgcolor="#0a0d0f",
                                       font_color="#c8d6df", height=200, showlegend=False,
                                       margin=dict(l=0,r=0,t=10,b=0),
                                       xaxis=dict(gridcolor="#1e2830"),
                                       yaxis=dict(gridcolor="#1e2830", title="kW"))
                    st.plotly_chart(fig3, use_container_width=True)

            # ── Tabla historial ────────────────────────────
            st.markdown("##### 📋 Historial de troncos")
            if not df_troncos.empty and "longitud_cm" in df_troncos.columns:
                cols_disp = [c for c in ["time","longitud_cm","duracion_ms","velocidad_cms","L1_A","L2_A","L3_A","potencia_kW"]
                             if c in df_t.columns]
                df_show = df_t[cols_disp].sort_values("time", ascending=False).head(20).copy()
                df_show.columns = [c.replace("_"," ").upper() for c in df_show.columns]
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.info("Sin registros — mueve el encoder para generar datos")

    except Exception as e:
        st.error(f"Error de conexión: {e}")

    time.sleep(refresh)
    st.cache_data.clear() if hasattr(st, 'cache_data') else None
    st.rerun()
