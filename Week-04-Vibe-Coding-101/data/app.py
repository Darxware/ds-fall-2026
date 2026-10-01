from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="MovieLens Dashboard", layout="wide")
st.title("🎬 MovieLens Dashboard")


@st.cache_data
def load():
    df = pd.read_csv(Path(__file__).parent / "movie_ratings.csv")
    df["genre_list"] = df["genres"].str.split("|")
    return df


df = load()

# ---------- Sidebar controls ----------
st.sidebar.header("Filters")
all_genres = sorted(df["genres"].str.split("|").explode().unique())
sel_genres = st.sidebar.multiselect("Genres (movie must have at least one)", all_genres, default=all_genres)
min_year, max_year = int(df["year"].min()), int(df["year"].max())
year_range = st.sidebar.slider("Movie release year", min_year, max_year, (min_year, max_year))
min_genre_ratings = st.sidebar.slider("Min ratings per genre (Q2)", 1, 1000, 100, step=10)
min_year_ratings = st.sidebar.slider("Min ratings per release year (Q3)", 1, 500, 50, step=10)

# Filter ratings: release-year range (drops the 30 rows with unknown year) + genre selection
f = df[df["year"].between(*year_range)]
f = f[f["genre_list"].apply(lambda g: any(x in sel_genres for x in g))]
st.caption(f"{len(f):,} ratings · {f['movie_id'].nunique():,} movies · {f['user_id'].nunique():,} users after filters")

if f.empty:
    st.warning("No data for the current filters.")
    st.stop()

# A multi-genre movie counts once in EACH of its genres (explode).
ex = f.explode("genre_list").rename(columns={"genre_list": "genre"})
ex = ex[ex["genre"].isin(sel_genres)]

# ---------- Q1 ----------
st.subheader("1. Genre breakdown")
st.markdown("Movies with several genres are counted **once in each genre**, so bars sum to more than the number of movies. Counts are distinct *rated movies*.")
q1 = ex.groupby("genre")["movie_id"].nunique().reset_index(name="movies").sort_values("movies", ascending=False)
st.altair_chart(
    alt.Chart(q1).mark_bar().encode(
        x=alt.X("movies:Q", title="Distinct rated movies"),
        y=alt.Y("genre:N", sort="-x", title=None),
        tooltip=["genre", "movies"],
    ).properties(height=max(200, 24 * len(q1))),
    width='stretch',
)

# ---------- Q2 ----------
st.subheader("2. Genre satisfaction")
st.markdown("Mean of **all individual ratings** in each genre (a multi-genre movie's ratings count toward each of its genres). Genres below the sidebar rating floor are hidden.")
q2 = ex.groupby("genre")["rating"].agg(mean_rating="mean", n="count").reset_index()
q2 = q2[q2["n"] >= min_genre_ratings].sort_values("mean_rating", ascending=False)
if q2.empty:
    st.info("No genres meet the rating floor.")
else:
    lo = q2.mean_rating.min()
    st.altair_chart(
        alt.Chart(q2).mark_bar().encode(
            x=alt.X("mean_rating:Q", title="Mean rating (axis starts at 3)", scale=alt.Scale(domain=[3, 4.5])),
            y=alt.Y("genre:N", sort="-x", title=None),
            color=alt.Color("mean_rating:Q", scale=alt.Scale(scheme="redyellowgreen", domain=[3, 4.2]), legend=None),
            tooltip=["genre", alt.Tooltip("mean_rating:Q", format=".3f"), alt.Tooltip("n:Q", title="ratings")],
        ).properties(height=max(200, 24 * len(q2))),
        width='stretch',
    )
    st.write(f"**Highest:** {q2.iloc[0].genre} ({q2.iloc[0].mean_rating:.2f}) · **Lowest:** {q2.iloc[-1].genre} ({q2.iloc[-1].mean_rating:.2f})")

# ---------- Q3 ----------
st.subheader("3. Mean rating by movie release year")
st.markdown("X-axis is the year the **movie was released**, not the year it was rated. Years with few ratings are hidden (sidebar) because their means are noisy.")
q3 = f.groupby("year")["rating"].agg(mean_rating="mean", n="count").reset_index()
q3 = q3[q3["n"] >= min_year_ratings]
if q3.empty:
    st.info("No release years meet the rating floor.")
else:
    st.altair_chart(
        alt.Chart(q3).mark_line(point=True).encode(
            x=alt.X("year:O", title="Release year", axis=alt.Axis(labelAngle=-90)),
            y=alt.Y("mean_rating:Q", title="Mean rating", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("year:O"), alt.Tooltip("mean_rating:Q", format=".3f"), alt.Tooltip("n:Q", title="ratings")],
        ).properties(height=350),
        width='stretch',
    )

# ---------- Q4 ----------
st.subheader("4. Best movies, with a ratings floor")
st.markdown("Ranked by mean rating among movies with at least *N* ratings. Compare the two floors side by side.")
floor_a = st.number_input("Floor A", 1, 500, 50)
floor_b = st.number_input("Floor B", 1, 500, 150)
movies = f.groupby(["movie_id", "title"])["rating"].agg(mean_rating="mean", n="count").reset_index()
cols = st.columns(2)
for col, floor in zip(cols, (floor_a, floor_b)):
    top = movies[movies["n"] >= floor].nlargest(5, "mean_rating")
    with col:
        st.markdown(f"**Top 5 with ≥ {floor} ratings**")
        if top.empty:
            st.info("No movies meet this floor.")
            continue
        st.altair_chart(
            alt.Chart(top).mark_bar().encode(
                x=alt.X("mean_rating:Q", title="Mean rating", scale=alt.Scale(domain=[3.5, 5])),
                y=alt.Y("title:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
                tooltip=["title", alt.Tooltip("mean_rating:Q", format=".3f"), alt.Tooltip("n:Q", title="ratings")],
            ).properties(height=220),
            width='stretch',
        )
