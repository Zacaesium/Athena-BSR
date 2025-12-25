import streamlit as st
import itertools
import pandas as pd

# ==============================================================================
# 1. ARCHITECTURE MOTEUR (CLASSES & LOGIQUE)
# ==============================================================================

class Stats:
    def __init__(self, **kwargs):
        # Stats universelles
        self.atk_flat = kwargs.get('atk_flat', 0)
        self.atk_pct = kwargs.get('atk_pct', 0)
        self.base_atk_mult = kwargs.get('base_atk_mult', 0) # +X% Base ATK
        self.crit_rate = kwargs.get('crit_rate', 0)
        self.crit_dmg = kwargs.get('crit_dmg', 0)
        self.slash_dmg = kwargs.get('slash_dmg', 0)
        self.all_dmg = kwargs.get('all_dmg', 0)
        self.weapon_stat_boost = kwargs.get('weapon_stat_boost', 0)
        
    def __add__(self, other):
        new = Stats()
        new.atk_flat = self.atk_flat + other.atk_flat
        new.atk_pct = self.atk_pct + other.atk_pct
        new.base_atk_mult = self.base_atk_mult + other.base_atk_mult
        new.crit_rate = self.crit_rate + other.crit_rate
        new.crit_dmg = self.crit_dmg + other.crit_dmg
        new.slash_dmg = self.slash_dmg + other.slash_dmg
        new.all_dmg = self.all_dmg + other.all_dmg
        new.weapon_stat_boost = self.weapon_stat_boost + other.weapon_stat_boost
        return new

class Effect:
    def __init__(self, trigger, type, value, condition=None):
        self.trigger = trigger # ex: "on_special_cast", "passive"
        self.type = type       # ex: "extra_hit_mult", "buff_skill_mv"
        self.value = value     # ex: 1.78, 0.20
        self.condition = condition

    def to_dict(self):
        return {"trigger": self.trigger, "type": self.type, "value": self.value}

class Item:
    def __init__(self, name, category, slot=None, set_name=None, stats=None, effects=None):
        self.name = name
        self.category = category # "stamp", "core", "weapon_stamp"
        self.slot = slot         # 1, 2, 3 (seulement pour stamps)
        self.set_name = set_name # "Rising Black Moon"
        self.stats = Stats(**(stats or {}))
        self.effects = [Effect(**e) if isinstance(e, dict) else e for e in (effects or [])]

# ==============================================================================
# 2. FONCTION DE CALCUL DES DÉGÂTS (LE CERVEAU)
# ==============================================================================

def calculate_dps_scenario(char_base, weapon_base, stamps, core, w_stamp, team_config):
    # 1. Aggrégation des Stats Items
    total_stats = Stats()
    all_items = stamps + [core, w_stamp]
    
    extra_effects = []
    
    for item in all_items:
        total_stats = total_stats + item.stats
        extra_effects.extend(item.effects)

    # 2. Bonus de Sets (Hardcodé pour l'instant car logique complexe)
    sets = [s.set_name for s in stamps]
    
    # Rising Black Moon (3pc)
    if sets.count("Rising Black Moon") >= 3:
        total_stats.slash_dmg += 0.11
        total_stats.base_atk_mult += 0.18
        # Note: Le bonus Spec DMG est géré via MV boost
        extra_effects.append(Effect("on_special_cast", "buff_mv_pct", 0.28))

    # Beast Tyrant (3pc) - Moyenne Pondérée
    if sets.count("Beast Tyrant") >= 3:
        total_stats.base_atk_mult += 0.16
        uptime = 0.66
        total_stats.atk_pct += (0.34 / 3) * uptime
        total_stats.crit_rate += (0.36 / 3) * uptime
        total_stats.all_dmg += (0.23 / 3) * uptime

    # 3. Calcul ATK
    # Boost Arme (Sundering Slash par ex)
    real_weapon_atk = weapon_base * (1 + total_stats.weapon_stat_boost)
    # Base Boost
    real_base_atk = (char_base + real_weapon_atk) * (1 + total_stats.base_atk_mult)
    # Final
    final_atk = real_base_atk * (1 + total_stats.atk_pct + team_config['buff_atk_pct']) + total_stats.atk_flat + team_config['buff_atk_flat']

    # 4. Calcul Crit
    final_cr = 0.05 + total_stats.crit_rate # 5% Base char
    
    # Passif Bond (Lien)
    bond_dmg = 0.08
    if final_cr >= 0.40: bond_dmg = 0.16
    elif final_cr >= 0.20: bond_dmg = 0.12
    bond_dmg += 0.15 # All Type Bonus
    bond_cd = 0.30
    
    final_cd = 0.50 + total_stats.crit_dmg + bond_cd + team_config['buff_crit_dmg']
    
    # Spirit Surge Logic (Cap Crit)
    if final_cr > 1.0:
        surplus = final_cr - 1.0
        final_cd += surplus * 1.75
        final_cr = 1.0
        
    crit_factor = 1 + (final_cr * final_cd)

    # 5. Damage Bucket
    dmg_mult = 1 + total_stats.slash_dmg + total_stats.all_dmg + bond_dmg + team_config['buff_dmg_bonus'] + 0.25 # Marque

    # 6. Simulation Attaque Spéciale (avec Effets Dynamiques)
    base_mv = 3.35 # Ichigo Special
    
    # Appliquer les buffs de MV (ex: RBM set)
    mv_boost = sum([e.value for e in extra_effects if e.type == "buff_mv_pct" and e.trigger == "on_special_cast"])
    current_mv = base_mv + mv_boost
    
    # Appliquer les Extra Hits (Afterimages, Gather Up core)
    # On cherche les effets 'extra_hit_mult'
    extra_hit_ratio = sum([e.value for e in extra_effects if e.type == "extra_hit_mult" and e.trigger == "on_special_cast"])
    
    # Formule approx Extra Hit (subit DEF mais profite des buffs)
    # On simule que l'afterimage est un coup séparé
    
    # 7. Résistance Ennemie
    res_mult = 1.72 # Avec Byakuya
    
    # Dégât du Coup Principal
    main_hit = final_atk * crit_factor * dmg_mult * res_mult * current_mv
    
    # Dégât des Extra Hits (Ratio * Main Hit * facteur correction défense si besoin)
    # Ici on assume qu'ils profitent de tout pareil
    extra_hits = main_hit * (extra_hit_ratio) 
    
    total_dps = main_hit + extra_hits
    
    return total_dps, final_atk, final_cr, final_cd

# ==============================================================================
# 3. INTERFACE STREAMLIT
# ==============================================================================

def main():
    st.set_page_config(page_title="Athena BSR Optimizer", layout="wide")
    st.title("⚔️ Athena: Bleach Soul Resonance Optimizer")

    # --- SESSION STATE (Base de Données) ---
    if 'inventory' not in st.session_state:
        # On charge tes données initiales ici
        st.session_state.inventory = {
            "stamps": [
                # RBM
                Item("RBM_1 (Lv30)", "stamp", slot=1, set_name="Rising Black Moon", stats={"atk_flat": 630, "atk_pct": 0.21, "crit_dmg": 0.153}),
                Item("RBM_2 (Lv15)", "stamp", slot=1, set_name="Rising Black Moon", stats={"atk_flat": 369, "slash_dmg": 0.117, "crit_rate": 0.038, "crit_dmg": 0.076}),
                Item("RBM_3 (Lv15)", "stamp", slot=2, set_name="Rising Black Moon", stats={"atk_flat": 247, "crit_rate": 0.038, "atk_pct": 0.05}),
                Item("RBM_4 (Lv1)", "stamp", slot=3, set_name="Rising Black Moon", stats={"crit_rate": 0.038, "atk_pct": 0.025}),
                # BT
                Item("BT_1 (Lv25)", "stamp", slot=1, set_name="Beast Tyrant", stats={"atk_flat": 585, "atk_pct": 0.23, "crit_dmg": 0.153}),
                Item("BT_2 (Lv25)", "stamp", slot=2, set_name="Beast Tyrant", stats={"crit_rate": 0.276, "crit_dmg": 0.153, "atk_pct": 0.025}),
                Item("BT_3 (Lv25)", "stamp", slot=3, set_name="Beast Tyrant", stats={"atk_pct": 0.23, "crit_rate": 0.076}),
            ],
            "cores": [
                Item("Getsuga Tangle", "core", stats={"atk_flat": 543, "slash_dmg": 0.20}),
                Item("Waiting for You", "core", stats={"atk_flat": 332, "all_dmg": 0.099}, effects=[Effect("on_special_cast", "buff_mv_pct", 0.875)]),
                Item("Gather Up! 13", "core", stats={"atk_flat": 100, "all_dmg": 0.064}, effects=[Effect("on_special_cast", "extra_hit_mult", 0.4375)])
            ],
            "w_stamps": [
                Item("Power of Hollowfication", "weapon_stamp", stats={"crit_rate": 0.15, "weapon_stat_boost": 0.50}, effects=[Effect("on_special_cast", "extra_hit_mult", 1.78)]),
                Item("Sundering Slash", "weapon_stamp", stats={"base_atk_mult": 0.15, "weapon_stat_boost": 0.25})
            ]
        }

    # --- SIDEBAR : CONFIG PERSO & TEAM ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.subheader("Ichigo Base Stats")
        char_base = st.number_input("Char Base ATK", value=605)
        weapon_base = st.number_input("Weapon Base ATK", value=908)
        
        st.subheader("Team Buffs (Byakuya/Urahara)")
        buff_atk_pct = st.number_input("Buff Team ATK % (0.60)", value=0.60)
        buff_atk_flat = st.number_input("Buff Team ATK Flat (540)", value=540)
        buff_crit_dmg = st.number_input("Buff Team Crit DMG (0.23)", value=0.23)
        buff_dmg_bonus = st.number_input("Buff Team DMG Bonus (0.40)", value=0.40)
        
        team_config = {
            "buff_atk_pct": buff_atk_pct, "buff_atk_flat": buff_atk_flat,
            "buff_crit_dmg": buff_crit_dmg, "buff_dmg_bonus": buff_dmg_bonus
        }

    # --- TABS PRINCIPAUX ---
    tab1, tab2, tab3 = st.tabs(["🚀 Optimisateur", "🎒 Gestion Inventaire", "📚 Manuel"])

    # --- TAB 1 : L'OPTIMISATEUR ---
    with tab1:
        st.subheader("Trouver le Meilleur Build")
        if st.button("Lancer l'Optimisation ATHENA", type="primary"):
            
            # Préparation des slots
            inv = st.session_state.inventory
            s1 = [s for s in inv['stamps'] if s.slot == 1]
            s2 = [s for s in inv['stamps'] if s.slot == 2]
            s3 = [s for s in inv['stamps'] if s.slot == 3]
            
            # Calcul Brut
            combinations = list(itertools.product(s1, s2, s3, inv['cores'], inv['w_stamps']))
            st.write(f"🔍 Analyse de {len(combinations)} combinaisons possibles...")
            
            best_dps = 0
            best_res = None
            
            progress_bar = st.progress(0)
            
            for i, (st1, st2, st3, core, wstamp) in enumerate(combinations):
                dps, atk, cr, cd = calculate_dps_scenario(char_base, weapon_base, [st1, st2, st3], core, wstamp, team_config)
                if dps > best_dps:
                    best_dps = dps
                    best_res = {
                        "stamps": [st1.name, st2.name, st3.name],
                        "core": core.name,
                        "wstamp": wstamp.name,
                        "stats": (atk, cr, cd)
                    }
                if i % 100 == 0:
                    progress_bar.progress(min(i / len(combinations), 1.0))
            
            progress_bar.progress(1.0)
            
            # Affichage Résultats
            st.success(f"🏆 MEILLEUR BUILD TROUVÉ : {best_dps:,.0f} Dégâts")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Arme Stamp:** {best_res['wstamp']}")
                st.info(f"**Core Stamp:** {best_res['core']}")
                st.write("**Stamps:**")
                for s in best_res['stamps']:
                    st.write(f"- {s}")
            
            with col2:
                atk, cr, cd = best_res['stats']
                st.metric("ATK Finale", f"{atk:.0f}")
                st.metric("Crit Rate", f"{cr*100:.1f}%")
                st.metric("Crit DMG", f"{cd*100:.0f}%")

    # --- TAB 2 : GESTION INVENTAIRE ---
    with tab2:
        st.subheader("Ajouter un nouvel objet")
        
        col_type, col_name = st.columns(2)
        new_type = col_type.selectbox("Type", ["stamp", "core", "weapon_stamp"])
        new_name = col_name.text_input("Nom de l'objet")
        
        col_slot, col_set = st.columns(2)
        new_slot = col_slot.selectbox("Slot (Stamp only)", [1, 2, 3], disabled=(new_type!="stamp"))
        new_set = col_set.text_input("Set (ex: Rising Black Moon)")
        
        st.write("--- Stats ---")
        c1, c2, c3, c4 = st.columns(4)
        s_atk_flat = c1.number_input("ATK Flat", 0)
        s_atk_pct = c2.number_input("ATK % (0.10 = 10%)", 0.0, 1.0, 0.0, step=0.01)
        s_cr = c3.number_input("Crit Rate", 0.0, 1.0, 0.0, step=0.01)
        s_cd = c4.number_input("Crit DMG", 0.0, 5.0, 0.0, step=0.01)
        
        c5, c6 = st.columns(2)
        s_base_mult = c5.number_input("Base ATK Boost", 0.0, 2.0, 0.0, step=0.01)
        s_weapon_boost = c6.number_input("Weapon Stats Boost", 0.0, 2.0, 0.0, step=0.01)

        st.write("--- Effet Spécial (Avancé) ---")
        eff_active = st.checkbox("Cet objet a un effet spécial ?")
        eff_trigger = "on_special_cast"
        eff_type = "extra_hit_mult"
        eff_val = 0.0
        
        if eff_active:
            ec1, ec2, ec3 = st.columns(3)
            eff_trigger = ec1.selectbox("Déclencheur", ["on_special_cast", "passive"])
            eff_type = ec2.selectbox("Type Effet", ["extra_hit_mult", "buff_mv_pct"])
            eff_val = ec3.number_input("Valeur (ex: 1.78)", 0.0, 10.0, 0.0)

        if st.button("Sauvegarder l'Objet"):
            stats_dict = {
                "atk_flat": s_atk_flat, "atk_pct": s_atk_pct,
                "crit_rate": s_cr, "crit_dmg": s_cd,
                "base_atk_mult": s_base_mult, "weapon_stat_boost": s_weapon_boost
            }
            effects_list = []
            if eff_active:
                effects_list.append({"trigger": eff_trigger, "type": eff_type, "value": eff_val})
            
            new_item = Item(new_name, new_type, slot=new_slot, set_name=new_set, stats=stats_dict, effects=effects_list)
            
            # Ajout à la base
            if new_type == "stamp": st.session_state.inventory['stamps'].append(new_item)
            elif new_type == "core": st.session_state.inventory['cores'].append(new_item)
            else: st.session_state.inventory['w_stamps'].append(new_item)
            
            st.success(f"{new_name} ajouté !")

        st.divider()
        st.write("### Inventaire Actuel")
        st.write(f"Stamps: {len(st.session_state.inventory['stamps'])}")
        st.write(f"Cores: {len(st.session_state.inventory['cores'])}")
        st.write(f"Weapon Stamps: {len(st.session_state.inventory['w_stamps'])}")

    with tab3:
        st.markdown("""
        ### 📚 Comment ajouter des effets ?
        Le logiciel comprend les effets suivants :
        
        **1. Extra Hit (Afterimages)**
        * Utiliser pour : Ichigo Weapon Stamp, Gather Up Core.
        * Trigger: `on_special_cast`
        * Type: `extra_hit_mult`
        * Valeur: Le ratio de l'attaque (ex: 1.78 pour Ichigo, 0.4375 pour Gather Up).
        
        **2. Buff Motion Value**
        * Utiliser pour : Waiting for You, RBM Set Bonus.
        * Trigger: `on_special_cast`
        * Type: `buff_mv_pct`
        * Valeur: % Ajouté au skill (ex: 0.28 pour 28%).
        """)

if __name__ == "__main__":
    main()
