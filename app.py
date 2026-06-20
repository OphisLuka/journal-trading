"""
Journal de trading crypto -- saisie + analyse comportementale
------------------------------------------------------------------
Application Streamlit qui permet de :
1. Saisir ses trades crypto au fur et a mesure (formulaire)
2. Les stocker dans un fichier CSV local (persistant entre les sessions)
3. Visualiser sa performance globale (gain/perte, taux de reussite...)
4. Detecter automatiquement des biais comportementaux connus en
   finance comportementale (revenge trading, surconfiance, trading
   nocturne, tilt) grace a des tests statistiques simples.

Lancement : streamlit run app.py
"""

import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from scipy import stats
import os

FICHIER_DONNEES = "historique_trades.csv"
COLONNES = ["date", "crypto", "direction", "prix_entree", "prix_sortie",
            "taille_position_eur", "resultat_pct", "gain_perte_eur"]

st.set_page_config(page_title="Journal de trading crypto", layout="wide")

# ----------------------------------------------------------------------
# FONCTIONS UTILITAIRES : charger / sauvegarder les donnees
# ----------------------------------------------------------------------
def charger_donnees():
    if os.path.exists(FICHIER_DONNEES):
        df = pd.read_csv(FICHIER_DONNEES, parse_dates=["date"])
        return df
    return pd.DataFrame(columns=COLONNES)


def sauvegarder_donnees(df):
    df.to_csv(FICHIER_DONNEES, index=False)


def calculer_resultat_pct(direction, prix_entree, prix_sortie):
    """
    Calcule le resultat (%) d'un trade a partir du prix d'entree et de
    sortie, selon la direction prise :
    - Long (pari a la hausse)  : on gagne si le prix monte
    - Short (pari a la baisse) : on gagne si le prix baisse
    """
    variation_pct = (prix_sortie - prix_entree) / prix_entree * 100
    if direction == "short":
        variation_pct = -variation_pct
    return variation_pct


def ajouter_trade(date, crypto, direction, prix_entree, prix_sortie, taille):
    df = charger_donnees()
    resultat_pct = calculer_resultat_pct(direction, prix_entree, prix_sortie)
    gain_perte_eur = taille * (resultat_pct / 100)
    nouveau_trade = pd.DataFrame([{
        "date": date,
        "crypto": crypto,
        "direction": direction,
        "prix_entree": prix_entree,
        "prix_sortie": prix_sortie,
        "taille_position_eur": taille,
        "resultat_pct": round(resultat_pct, 3),
        "gain_perte_eur": round(gain_perte_eur, 2),
    }])
    df = pd.concat([df, nouveau_trade], ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    sauvegarder_donnees(df)
    return df


# ----------------------------------------------------------------------
# FONCTION : comparer deux groupes de trades statistiquement
# ----------------------------------------------------------------------
def comparer_groupes(groupe_a, groupe_b, variable):
    """Renvoie (moyenne_a, moyenne_b, p_value, significatif) pour une variable donnee."""
    if len(groupe_a) < 2 or len(groupe_b) < 2:
        return None
    moyenne_a = groupe_a[variable].mean()
    moyenne_b = groupe_b[variable].mean()
    t_stat, p_value = stats.ttest_ind(groupe_a[variable], groupe_b[variable], equal_var=False)
    return moyenne_a, moyenne_b, p_value, p_value < 0.05


# ----------------------------------------------------------------------
# PREPARATION DES DONNEES POUR L'ANALYSE DE BIAIS
# ----------------------------------------------------------------------
def preparer_indicateurs(df):
    """Ajoute les colonnes necessaires a la detection des biais comportementaux."""
    df = df.sort_values("date").reset_index(drop=True)
    df["resultat_precedent"] = df["resultat_pct"].shift(1).fillna(0)
    df["trade_apres_perte"] = df["resultat_precedent"] < 0
    df["trade_apres_gain_fort"] = df["resultat_precedent"] > 3
    df["heure"] = pd.to_datetime(df["date"]).dt.hour
    df["nocturne"] = df["heure"].apply(lambda h: h >= 22 or h <= 3)

    compteur = 0
    serie = []
    for p in (df["resultat_pct"] < 0):
        compteur = compteur + 1 if p else 0
        serie.append(compteur)
    df["pertes_consecutives_avant"] = [0] + serie[:-1]
    return df


# ----------------------------------------------------------------------
# INTERFACE : BARRE LATERALE (saisie d'un nouveau trade)
# ----------------------------------------------------------------------
st.sidebar.header("➕ Ajouter un trade")
with st.sidebar.form("formulaire_trade", clear_on_submit=True):
    date_trade = st.date_input("Date du trade")
    heure_trade = st.time_input("Heure du trade")
    crypto = st.selectbox("Crypto", ["BTC", "ETH", "SOL", "BNB", "XRP", "Autre"])
    direction = st.radio(
        "Direction", ["long", "short"], horizontal=True,
        help="Long = tu paries à la hausse (achat classique). Short = tu paries à la baisse."
    )
    prix_entree = st.number_input("Prix d'entrée (EUR)", min_value=0.0, step=1.0, value=0.0)
    prix_sortie = st.number_input("Prix de sortie (EUR)", min_value=0.0, step=1.0, value=0.0)
    taille = st.number_input(
        "Taille de la position (EUR)", min_value=0.0, step=10.0, value=100.0,
        help="Le montant en euros que tu as réellement engagé sur ce trade — "
             "pas le prix du Bitcoin. Ex: tu peux miser 100€ même si le BTC vaut 95 000€."
    )
    valider = st.form_submit_button("Enregistrer le trade")

    if valider:
        if prix_entree <= 0 or prix_sortie <= 0:
            st.sidebar.error("Renseigne un prix d'entrée et de sortie supérieurs à 0.")
        else:
            date_complete = pd.Timestamp.combine(date_trade, heure_trade)
            ajouter_trade(date_complete, crypto, direction, prix_entree, prix_sortie, taille)
            st.sidebar.success("Trade enregistré !")

st.sidebar.markdown("---")
st.sidebar.caption(
    "Les données sont enregistrées localement dans 'historique_trades.csv'. "
    "Tu peux aussi remplir ce fichier directement (Excel, etc.) avec les "
    "colonnes : date, crypto, direction, prix_entree, prix_sortie, taille_position_eur."
)

# ----------------------------------------------------------------------
# CONTENU PRINCIPAL
# ----------------------------------------------------------------------
st.title("📊 Journal de trading crypto")
st.caption("Suivi de performance et détection de biais comportementaux à partir de ton propre historique.")

df = charger_donnees()

if df.empty:
    st.info("Aucun trade enregistré pour le moment. Ajoute ton premier trade dans le menu de gauche, "
            "ou importe un fichier CSV ci-dessous.")
else:
    df = preparer_indicateurs(df)

    # --- Métriques globales ---
    gain_total = df["gain_perte_eur"].sum()
    taux_reussite = (df["resultat_pct"] > 0).mean()
    gains = df.loc[df["gain_perte_eur"] > 0, "gain_perte_eur"].sum()
    pertes = abs(df.loc[df["gain_perte_eur"] < 0, "gain_perte_eur"].sum())
    profit_factor = gains / pertes if pertes > 0 else np.nan

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Nombre de trades", len(df))
    col2.metric("Gain / perte total", f"{gain_total:+.2f} €")
    col3.metric("Taux de réussite", f"{taux_reussite:.1%}")
    col4.metric("Profit factor", f"{profit_factor:.2f}" if not np.isnan(profit_factor) else "N/A")

    st.markdown("---")

    # --- Graphiques ---
    col_gauche, col_droite = st.columns(2)

    with col_gauche:
        st.subheader("Évolution du capital cumulé")
        df["capital_cumule"] = df["gain_perte_eur"].cumsum()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(df["date"], df["capital_cumule"], color="steelblue")
        ax.axhline(0, color="grey", linewidth=0.8, linestyle="--")
        ax.set_ylabel("EUR")
        fig.autofmt_xdate(rotation=30)
        st.pyplot(fig)

    with col_droite:
        st.subheader("Performance moyenne par heure")
        if df["heure"].nunique() > 1:
            perf_heure = df.groupby("heure")["resultat_pct"].mean()
            couleurs = ["indianred" if (h >= 22 or h <= 3) else "steelblue" for h in perf_heure.index]
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(perf_heure.index, perf_heure.values, color=couleurs)
            ax.axhline(0, color="black", linewidth=0.8)
            ax.set_xlabel("Heure de la journée")
            ax.set_ylabel("Résultat moyen (%)")
            st.pyplot(fig)
        else:
            st.caption("Ajoute des trades à différentes heures pour voir ce graphique.")

    st.markdown("---")
    st.subheader("🔍 Détection de biais comportementaux")
    st.caption(
        "Pour chaque biais, on compare deux groupes de trades avec un test statistique (test t de Student). "
        "Une différence est jugée significative si la p-value est inférieure à 0.05 "
        "(moins de 5% de chances que l'écart observé soit dû au hasard)."
    )

    biais_detectes = []

    # Biais 1 : revenge trading
    res = comparer_groupes(df[df["trade_apres_perte"]], df[~df["trade_apres_perte"]], "taille_position_eur")
    if res:
        m_a, m_b, p, sig = res
        biais_detectes.append(("Revenge trading", "Taille de position après une perte vs après un gain",
                                m_a, m_b, p, sig,
                                "Tu trades avec des positions plus grosses après une perte, signe possible "
                                "de tentative de \"se refaire\"." if sig and m_a > m_b else None))

    # Biais 2 : surconfiance
    res = comparer_groupes(df[df["trade_apres_gain_fort"]], df[~df["trade_apres_gain_fort"]], "taille_position_eur")
    if res:
        m_a, m_b, p, sig = res
        biais_detectes.append(("Surconfiance", "Taille de position après un gros gain (>3%) vs sinon",
                                m_a, m_b, p, sig,
                                "Tu augmentes la taille de tes positions après un gros gain, signe possible "
                                "de surconfiance." if sig and m_a > m_b else None))

    # Biais 3 : trading nocturne
    res = comparer_groupes(df[df["nocturne"]], df[~df["nocturne"]], "resultat_pct")
    if res:
        m_a, m_b, p, sig = res
        biais_detectes.append(("Trading nocturne", "Résultat (%) des trades nocturnes (22h-3h) vs en journée",
                                m_a, m_b, p, sig,
                                "Tes trades nocturnes sont nettement moins bons que ceux de la journée."
                                if sig and m_a < m_b else None))

    # Biais 4 : tilt
    res = comparer_groupes(df[df["pertes_consecutives_avant"] >= 3], df[df["pertes_consecutives_avant"] < 3], "resultat_pct")
    if res:
        m_a, m_b, p, sig = res
        biais_detectes.append(("Tilt", "Résultat (%) après 3+ pertes consécutives vs en situation normale",
                                m_a, m_b, p, sig,
                                "Après plusieurs pertes d'affilée, tes résultats se dégradent encore plus."
                                if sig and m_a < m_b else None))

    if len(df) < 15:
        st.warning("Moins de 15 trades enregistrés : les tests statistiques ci-dessous manquent encore "
                   "de données pour être fiables. Continue à enregistrer tes trades !")

    for nom, description, m_a, m_b, p, sig, message in biais_detectes:
        with st.expander(f"{'⚠️' if (sig and message) else '✅'}  {nom}"):
            st.write(description)
            st.write(f"Groupe 1 : {m_a:+.3f}  |  Groupe 2 : {m_b:+.3f}  |  p-value = {p:.4f}")
            if sig and message:
                st.warning(message)
            elif sig:
                st.info("Différence statistiquement significative, mais dans le sens favorable — pas d'alerte ici.")
            else:
                st.success("Pas de différence statistiquement significative détectée sur ce biais.")

    st.markdown("---")
    st.subheader("📋 Historique complet des trades")
    st.dataframe(df[COLONNES].sort_values("date", ascending=False), use_container_width=True)

# ----------------------------------------------------------------------
# IMPORT D'UN FICHIER EXTERNE (ex: export Binance adapté)
# ----------------------------------------------------------------------
st.markdown("---")
st.subheader("📥 Importer un fichier CSV existant")
st.caption("Colonnes attendues : date, crypto, direction, prix_entree, prix_sortie, taille_position_eur")
fichier_importe = st.file_uploader("Choisir un fichier CSV", type="csv")
if fichier_importe is not None:
    df_importe = pd.read_csv(fichier_importe, parse_dates=["date"])
    if "resultat_pct" not in df_importe.columns:
        df_importe["resultat_pct"] = df_importe.apply(
            lambda r: calculer_resultat_pct(r["direction"], r["prix_entree"], r["prix_sortie"]), axis=1
        ).round(3)
    if "gain_perte_eur" not in df_importe.columns:
        df_importe["gain_perte_eur"] = df_importe["taille_position_eur"] * (df_importe["resultat_pct"] / 100)
    df_existant = charger_donnees()
    df_final = pd.concat([df_existant, df_importe], ignore_index=True).drop_duplicates()
    sauvegarder_donnees(df_final)
    st.success(f"{len(df_importe)} trades importés et fusionnés avec l'historique existant.")
    st.rerun()
