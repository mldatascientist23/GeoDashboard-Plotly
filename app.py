import os
import io
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import wbdata
import plotly.io as pio
import collections; import collections.abc
from moviepy.editor import ImageSequenceClip
import base64

# ─── PATCH for Python 3.10+ wbdata ─────────────────────────────
collections.Sequence = collections.abc.Sequence

# ─── PAGE CONFIG ───────────────────────────────────────────────
st.set_page_config(
    page_title="GeoDashboard",
    layout="wide",
    page_icon="assets/favicon.ico"
)

# ─── HEADER ────────────────────────────────────────────────────
st.markdown("""
    <style>
        .header-container {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-top: -40px;
            margin-bottom: 0;
        }
        .logo-img {
            height: 50px;
            width: 50px;
            object-fit: contain;
        }
        .title-text {
            font-size: 2.3em;
            font-weight: 700;
            color: #ff4b4b;
            margin: 0;
            padding: 0;
        }
        .description-text {
            font-size: 1.1em;
            color: #555;
            margin-top: -0.3rem;
            margin-bottom: 1.5rem;
        }
        .footer {
            margin-top: 4rem;
            font-size: 0.9em;
            text-align: center;
            color: #999;
        }
    </style>
""", unsafe_allow_html=True)

# Embed logo from assets/logo.png as base64
logo_path = "assets/logo.png"
logo_base64 = base64.b64encode(open(logo_path, "rb").read()).decode()

st.markdown(f"""
    <div class="header-container">
        <img src="data:image/png;base64,{logo_base64}" class="logo-img">
        <div>
            <div class="title-text">Global GeoDashboard 🌍</div>
            <div class="description-text">
                Interactive World Bank choropleths—with PNG, GIF & MP4 exports, plus trend lines.
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# ─── INDICATORS ───────────────────────────────────────────────
metrics = {
  'CO₂ Emissions (metric tons per capita)': 'EN.ATM.CO2E.PC',
  'GDP per Capita (current US$)':            'NY.GDP.PCAP.CD',
  'Population':                              'SP.POP.TOTL',
  'Life Expectancy':                         'SP.DYN.LE00.IN'
}

# ─── COUNTRY LOOKUP ────────────────────────────────────────────
country_list = wbdata.get_country()
iso_map      = {c['name']: c['id'] for c in country_list}
all_countries= list(iso_map.keys())

# ─── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    selected_countries = st.multiselect("Select Countries", all_countries, default=["Pakistan","India"])
    selected_metrics   = st.multiselect("Select Metric/s", list(metrics.keys()), default=["GDP per Capita (current US$)"])
    theme             = st.radio("Theme", ["Light","Dark"], index=0)
    fps               = st.slider("Animation FPS", 1, 5, 2)

# ─── DATE RANGE ────────────────────────────────────────────────
start_date = datetime.datetime(2000,1,1)
end_date   = datetime.datetime(2022,1,1)

# ─── FRAME FOLDER CLEANUP ──────────────────────────────────────
FRAME_DIR = "frame"
os.makedirs(FRAME_DIR, exist_ok=True)
for fname in os.listdir(FRAME_DIR):
    if fname.lower().endswith((".png",".gif",".mp4")):
        os.remove(os.path.join(FRAME_DIR, fname))

# ─── MAIN ──────────────────────────────────────────────────────
if not selected_countries or not selected_metrics:
    st.warning("Please select at least one country and one metric.")
else:
    iso_list = [iso_map[c] for c in selected_countries if c in iso_map]

    for metric_name in selected_metrics:
        code = metrics[metric_name]

        try:
            df = wbdata.get_dataframe(
                indicators={code: metric_name},
                country=iso_list,
                data_date=(start_date, end_date),
                convert_date=True
            ).reset_index().dropna()
            df['Year'] = df['date'].dt.year
            df.rename(columns={'country':'Country'}, inplace=True)

            if df.empty:
                st.warning(f"No data for {metric_name}.")
                continue

            fig = px.choropleth(
                df,
                locations="Country",
                locationmode="country names",
                color=metric_name,
                animation_frame=df["Year"].astype(str),
                color_continuous_scale=(px.colors.sequential.Viridis 
                                        if theme=="Dark" 
                                        else px.colors.sequential.Plasma),
                title=f"{metric_name} (2000–2022)"
            )
            fig.update_geos(projection_type="natural earth",
                            showcoastlines=True, showcountries=True)
            fig.update_layout(
                coloraxis_colorbar=dict(
                    title=metric_name,
                    tickvals=df[metric_name].quantile([0.1,0.5,0.9]).round(2),
                    ticktext=[f"{v:.2e}" for v in df[metric_name].quantile([0.1,0.5,0.9])]
                ),
                template="plotly_dark" if theme=="Dark" else "plotly_white"
            )

            st.subheader(metric_name)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander(f"📈 Trend over time: {metric_name}", expanded=True):
                trend_df = df.pivot(index="Year", columns="Country", values=metric_name)
                st.line_chart(trend_df, use_container_width=True)

            years = sorted(df['Year'].unique())
            frame_paths = []
            for yr in years:
                dfx = df[df['Year']==yr]
                f = px.choropleth(
                    dfx,
                    locations="Country",
                    locationmode="country names",
                    color=metric_name,
                    hover_name="Country",
                    color_continuous_scale=(px.colors.sequential.Viridis 
                                            if theme=="Dark" 
                                            else px.colors.sequential.Plasma),
                    title=f"{metric_name} — {yr}"
                )
                f.update_geos(projection_type="natural earth")
                f.update_layout(template="plotly_dark" if theme=="Dark" 
                                else "plotly_white")
                out = os.path.join(FRAME_DIR, f"{code}_{yr}.png")
                pio.write_image(f, out, format="png")
                frame_paths.append(out)

            clip    = ImageSequenceClip(frame_paths, fps=fps)
            gif_p   = os.path.join(FRAME_DIR, f"{code}.gif")
            mp4_p   = os.path.join(FRAME_DIR, f"{code}.mp4")
            clip.write_gif(gif_p, fps=fps)
            clip.write_videofile(mp4_p, fps=fps,
                                 codec="libx264", audio=False,
                                 verbose=False, logger=None)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("📸 Download PNG",
                                   data=open(frame_paths[-1],"rb").read(),
                                   file_name=f"{code}_{years[-1]}.png",
                                   mime="image/png")
            with c2:
                st.download_button("📺 Download GIF",
                                   data=open(gif_p,"rb").read(),
                                   file_name=f"{code}.gif",
                                   mime="image/gif")
            with c3:
                st.download_button("🎞️ Download MP4",
                                   data=open(mp4_p,"rb").read(),
                                   file_name=f"{code}.mp4",
                                   mime="video/mp4")

            with st.expander("Show raw data"):
                st.dataframe(df)

        except Exception as e:
            st.error(f"❌ Error with {metric_name}: {e}")

# ─── FOOTER ─────────────────────────────────────────────────────
st.markdown("""
    <div class="footer">
        Created by: <strong>Engr. Hamesh Raj</strong> | Powered by Streamlit & Plotly
    </div>
""", unsafe_allow_html=True)
