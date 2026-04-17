# -*- coding: utf-8 -*-
"""\
Outil LangPack REAPER : remplacement par numéros de ligne + collage (append) d'un fichier SWS.

Fonctionne en double-clic Windows :
- travaille dans le dossier du script
- affiche un menu (1/2/3)
- écrit un log "langpack_tool_log.txt"
- pause en fin d'exécution (optionnel)

MENU :
1) Replace : applique MES_MODIFS au fichier REAPER
2) Paste SWS : colle le fichier SWS à la fin du fichier REAPER (avec séparateurs)
3) Replace & Paste SWS : fait les deux

NOUVEAU : option anti-doublon SWS
- Si ANTI_DOUBLON_SWS=True, le script détecte si le bloc SWS est déjà présent
  (les 3 séparateurs consécutifs) et évite de le recoller une seconde fois.
\
"""

# =================================================================
# 0) FICHIERS (AU DÉBUT)
# =================================================================
# Fichier LangPack principal (REAPER)
FICHIER_REAPER = "FULL_spanish_R766.txt"  # <-- à adapter

# Fichier SWS (à coller à la suite). Mets le nom exact (même dossier que le script)
FICHIER_SWS = "Turkish_R766.txt"  # <-- à adapter

# =================================================================
# 0b) OPTIONS (AU DÉBUT)
# =================================================================
PREFIX_SORTIE = "FULL_"           # Préfixe du fichier de sortie
OUT_EXTENSION = ".ReaperLangPack"   # Extension du fichier de sortie (au lieu de .txt)

FAIRE_BACKUP = True            # Crée un .bak du fichier REAPER
BACKUP_SWS = False             # True = fait aussi un .bak du fichier SWS
DRY_RUN = False                # True = n'écrit rien, affiche seulement un rapport
MODE_STRICT = False            # True = stoppe si une ligne est invalide/hors limites
PAUSE_FIN = True               # True = garde la fenêtre ouverte en fin d'exécution
LOG_FICHIER = True             # True = écrit un fichier log à côté du script

# Anti-doublon SWS : si True, évite de recoller le bloc SWS si déjà présent
ANTI_DOUBLON_SWS = True

# Séparateurs demandés (ajoutés avant le contenu SWS)
SEPARATEUR_1 = ";----------------;"
SEPARATEUR_2 = ";----------SWS---------------;"
SEPARATEUR_3 = ";----------------------;"

# Optionnel : charger des modifs depuis un JSON (en plus du dictionnaire ci-dessous)
# Format JSON : { "12": "contenu", "58": "contenu", ... }
MODIFS_JSON_PATH = None        # ex: "modifs.json"

# =================================================================
# 1) DICTIONNAIRE DE MODIFICATIONS (Numéro de ligne -> Ligne complète)
# =================================================================
# IMPORTANT : la valeur doit être la ligne complète à écrire (sans \n).
MES_MODIFS = {
    # Exemple :
    # 108: "5326D4DC339DAE86=Incrustar:",
    # 109: "D09B05DC6153712A=Regiones y marcadores",
}

# =================================================================
# 2) CODE
# =================================================================
import json
from pathlib import Path
from typing import Dict, Tuple


def _script_dir() -> Path:
    """Dossier du script (important en double-clic Windows)."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def _log_path() -> Path:
    return _script_dir() / "langpack_tool_log.txt"


def log(msg: str) -> None:
    print(msg)
    if LOG_FICHIER:
        try:
            with _log_path().open("a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass


def charger_modifs_json(path: Path) -> Dict[int, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    modifs: Dict[int, str] = {}
    for k, v in data.items():
        num = int(k)
        if not isinstance(v, str):
            raise ValueError(f"Valeur invalide pour la ligne {k} : attendu str")
        modifs[num] = v
    return modifs


def detecter_newline(contenu: str) -> str:
    crlf = contenu.count("\r\n")
    lf = contenu.count("\n")
    if crlf > 0 and crlf >= lf * 0.5:
        return "\r\n"
    return "\n"


def appliquer_modifs(lignes: list, modifs: Dict[int, str], strict: bool) -> Tuple[list, int, int]:
    nb_modifs = 0
    nb_hors = 0

    for num_ligne in sorted(modifs.keys()):
        if num_ligne < 1:
            msg = f"Numéro de ligne invalide (>=1) : {num_ligne}"
            if strict:
                raise ValueError(msg)
            log(f"[ALERTE] {msg}")
            nb_hors += 1
            continue

        idx = num_ligne - 1
        if idx < len(lignes):
            lignes[idx] = modifs[num_ligne]
            nb_modifs += 1
        else:
            msg = f"Ligne {num_ligne} hors limites (max={len(lignes)})"
            if strict:
                raise IndexError(msg)
            log(f"[ALERTE] {msg}")
            nb_hors += 1

    return lignes, nb_modifs, nb_hors


def lire_texte_utf8sig(path: Path) -> str:
    """Lit en utf-8-sig (gère BOM)."""
    return path.read_text(encoding="utf-8-sig")


def ecrire_texte_utf8sig(path: Path, contenu: str) -> None:
    """Écrit en utf-8-sig (avec BOM)."""
    path.write_text(contenu, encoding="utf-8-sig")


def faire_backup(path: Path) -> None:
    backup_path = path.with_suffix(path.suffix + ".bak")
    contenu = lire_texte_utf8sig(path)
    ecrire_texte_utf8sig(backup_path, contenu)
    log(f"[INFO] Backup créé : {backup_path.name}")


def operation_replace(contenu_reaper: str, modifs: Dict[int, str]) -> Tuple[str, int, int]:
    """Retourne (contenu_modifié, nb_modifs, nb_hors)."""
    newline = detecter_newline(contenu_reaper)
    lignes = contenu_reaper.splitlines()

    lignes_mod, nb_modifs, nb_hors = appliquer_modifs(lignes, modifs, strict=MODE_STRICT)
    contenu_mod = newline.join(lignes_mod) + newline

    return contenu_mod, nb_modifs, nb_hors


def bloc_sws_present(contenu_reaper: str) -> bool:
    """Détecte si le bloc SWS (les 3 séparateurs consécutifs) est déjà présent."""
    # On accepte \n ou \r\n entre les lignes.
    # Pour éviter les faux positifs, on vérifie la présence des 3 séparateurs dans l'ordre.
    # On cherche la séquence complète avec un simple test de sous-chaîne sur une version normalisée.
    normalise = contenu_reaper.replace("\r\n", "\n")
    motif = "\n".join([SEPARATEUR_1, SEPARATEUR_2, SEPARATEUR_3])
    return motif in normalise


def operation_paste_sws(contenu_reaper: str, path_sws: Path) -> str:
    """Colle le contenu SWS à la fin de contenu_reaper avec séparateurs."""
    sws_contenu = lire_texte_utf8sig(path_sws)  # BOM retiré si présent

    newline = detecter_newline(contenu_reaper)
    if not contenu_reaper.endswith(("\n", "\r\n")):
        contenu_reaper += newline

    # Séparateurs EXACTEMENT comme demandé (sur 3 lignes)
    bloc_sep = newline.join([SEPARATEUR_1, SEPARATEUR_2, SEPARATEUR_3]) + newline

    contenu_final = contenu_reaper + bloc_sep + sws_contenu
    if not contenu_final.endswith(("\n", "\r\n")):
        contenu_final += newline

    return contenu_final


def choisir_mode() -> int:
    log("\nChoisis une action :")
    log("  1 - Replace")
    log("  2 - Paste SWS")
    log("  3 - Replace & Paste SWS")

    while True:
        choix = input("Ton choix (1/2/3) : ").strip()
        if choix in {"1", "2", "3"}:
            return int(choix)
        log("[ALERTE] Choix invalide. Tape 1, 2 ou 3.")


def main() -> None:
    # Reset log
    if LOG_FICHIER:
        try:
            _log_path().unlink(missing_ok=True)
        except Exception:
            pass

    base_dir = _script_dir()
    log("--- DÉMARRAGE ---")
    log(f"Dossier du script : {base_dir}")

    path_reaper = (base_dir / FICHIER_REAPER) if not Path(FICHIER_REAPER).is_absolute() else Path(FICHIER_REAPER)
    path_sws = (base_dir / FICHIER_SWS) if not Path(FICHIER_SWS).is_absolute() else Path(FICHIER_SWS)

    if not path_reaper.exists():
        log(f"[ERREUR] Fichier REAPER introuvable : {path_reaper}")
        return

    # Charge modifs
    modifs = dict(MES_MODIFS)
    if MODIFS_JSON_PATH:
        json_path = (base_dir / MODIFS_JSON_PATH) if not Path(MODIFS_JSON_PATH).is_absolute() else Path(MODIFS_JSON_PATH)
        if not json_path.exists():
            log(f"[ERREUR] JSON introuvable : {json_path}")
            return
        modifs.update(charger_modifs_json(json_path))
        log(f"[INFO] Modifs JSON chargées : {json_path.name} ({len(modifs)} entrée(s))")

    mode = choisir_mode()

    if mode in (2, 3) and not path_sws.exists():
        log(f"[ERREUR] Fichier SWS introuvable : {path_sws}")
        return

    contenu_courant = lire_texte_utf8sig(path_reaper)

    # Replace
    if mode in (1, 3):
        if not modifs:
            log("[ALERTE] Aucune modification définie : Replace ne changera rien (copie identique).")
        contenu_courant, nb_modifs, nb_hors = operation_replace(contenu_courant, modifs)
        log(f"[INFO] Replace : {nb_modifs} modif(s), {nb_hors} hors limite(s).")

    # Paste SWS (avec anti-doublon)
    if mode in (2, 3):
        if ANTI_DOUBLON_SWS and bloc_sws_present(contenu_courant):
            log("[INFO] Anti-doublon SWS : bloc déjà présent, collage ignoré.")
        else:
            contenu_courant = operation_paste_sws(contenu_courant, path_sws)
            log("[INFO] Paste SWS : contenu SWS ajouté en fin de fichier.")

    # Sortie en .ReaperLangPack
    out_path = path_reaper.with_name(PREFIX_SORTIE + path_reaper.stem + OUT_EXTENSION)

    if DRY_RUN:
        log(f"[DRY-RUN] Aucune écriture. Sortie prévue : {out_path.resolve()}")
        return

    # Backups
    if FAIRE_BACKUP:
        faire_backup(path_reaper)
    if BACKUP_SWS and path_sws.exists():
        faire_backup(path_sws)

    # Écrit la sortie
    ecrire_texte_utf8sig(out_path, contenu_courant)
    log(f"[SUCCÈS] Fichier généré : {out_path.name}")
    log(f"         Emplacement : {out_path.resolve()}")
    log("--- FIN ---")


if __name__ == "__main__":
    try:
        main()
    finally:
        if PAUSE_FIN:
            try:
                input("\nTerminé. Appuie sur Entrée pour fermer...")
            except Exception:
                pass
