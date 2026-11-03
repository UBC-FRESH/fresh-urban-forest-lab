"""Species groups, urban allometry, and simple annual growth.

The equations are deliberately transparent and conservative. They are not a substitute
for a locally calibrated growth model, but they let the prototype answer the questions
that matter at the concept stage: how big is the canopy, how much carbon is stored, and
how does a planting or removal change those values over time.

The biomass equation follows the generalised diameter-based model in Jenkins et al.
(2003), using the softwood and hardwood coefficients. Carbon is half of above-ground
biomass; roots and dead wood are excluded.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from fresh_urban_forest.models import SpeciesGroup, TreeRecord

CONIFER_WORDS: frozenset[str] = frozenset(
    {
        "cedar",
        "cypress",
        "douglas",
        "fir",
        "hemlock",
        "juniper",
        "larch",
        "pine",
        "redwood",
        "sequoia",
        "spruce",
        "yew",
        "thuja",
        "picea",
        "pinus",
        "abies",
        "tsuga",
        "taxus",
        "chamaecyparis",
        "cupressus",
        "juniperus",
        "pseudotsuga",
        "metasequoia",
        "cryptomeria",
        "sciadopitys",
        "araucaria",
        "cedrus",
        "calocedrus",
        "sequoiadendron",
    }
)

DECIDUOUS_WORDS: frozenset[str] = frozenset(
    {
        "alder",
        "apple",
        "ash",
        "aspen",
        "beech",
        "birch",
        "basswood",
        "catalpa",
        "cherry",
        "chestnut",
        "cottonwood",
        "crabapple",
        "dogwood",
        "elm",
        "eucalyptus",
        "fig",
        "ginkgo",
        "hawthorn",
        "hickory",
        "hornbeam",
        "horsechestnut",
        "linden",
        "locust",
        "magnolia",
        "maple",
        "oak",
        "olive",
        "pear",
        "persimmon",
        "plane",
        "plum",
        "poplar",
        "rowan",
        "serviceberry",
        "sweetgum",
        "sycamore",
        "tulip",
        "walnut",
        "willow",
        "zelkova",
        "acer",
        "quercus",
        "betula",
        "prunus",
        "pyrus",
        "malus",
        "fraxinus",
        "ulmus",
        "fagus",
        "salix",
        "populus",
        "alnus",
        "carpinus",
        "tilia",
        "aesculus",
        "cornus",
        "crataegus",
        "sorbus",
        "amelanchier",
        "platanus",
        "juglans",
        "carya",
        "gleditsia",
        "robinia",
        "liriodendron",
        "liquidambar",
        "diospyros",
        "ficus",
        "olea",
        "nyssa",
        "celtis",
        "ostrya",
        "cercis",
        "sophora",
        "arbutus",
        "sambucus",
        "rhododendron",
        "viburnum",
        "syringa",
    }
)

NATIVE_WORDS: frozenset[str] = frozenset(
    {
        "douglas fir",
        "western red cedar",
        "western hemlock",
        "sitka spruce",
        "grand fir",
        "amabilis fir",
        "subalpine fir",
        "lodgepole pine",
        "shore pine",
        "western white pine",
        "pacific yew",
        "bigleaf maple",
        "red alder",
        "black cottonwood",
        "paper birch",
        "garry oak",
        "arbutus",
        "pacific dogwood",
        "cascara",
        "salmonberry",
        "thimbleberry",
        "red elderberry",
        "snowberry",
        "oceanspray",
        "nootka rose",
        "sword fern",
        "salal",
        "pseudotsuga menziesii",
        "thuja plicata",
        "tsuga heterophylla",
        "picea sitchensis",
        "abies grandis",
        "abies amabilis",
        "pinus contorta",
        "pinus monticola",
        "taxus brevifolia",
        "acer macrophyllum",
        "alnus rubra",
        "populus trichocarpa",
        "betula papyrifera",
        "quercus garryana",
        "arbutus menziesii",
        "cornus nuttallii",
        "rhamnus purshiana",
        "rubus spectabilis",
        "rubus parviflorus",
        "sambucus racemosa",
        "symphoricarpos albus",
        "holodiscus discolor",
        "rosa nutkana",
    }
)


@dataclass(frozen=True, slots=True)
class GrowthProfile:
    """Allometric and growth parameters for one species group.

    Attributes
    ----------
    group : str
        Species group name.
    max_dbh_cm : float
        Asymptotic diameter at breast height in centimetres.
    max_height_m : float
        Asymptotic height in metres.
    dbh_growth_cm_per_year : float
        Maximum annual diameter increment at small sizes.
    crown_ratio : float
        Default live-crown ratio, 0 to 1.
    height_coefficient : float
        Coefficient in the height-diameter power law.
    height_exponent : float
        Exponent in the height-diameter power law.
    crown_coefficient : float
        Coefficient in the crown-width power law.
    crown_exponent : float
        Exponent in the crown-width power law.
    """

    group: SpeciesGroup
    max_dbh_cm: float
    max_height_m: float
    dbh_growth_cm_per_year: float
    crown_ratio: float
    height_coefficient: float
    height_exponent: float
    crown_coefficient: float
    crown_exponent: float


PROFILES: dict[SpeciesGroup, GrowthProfile] = {
    "conifer": GrowthProfile(
        group="conifer",
        max_dbh_cm=180.0,
        max_height_m=65.0,
        dbh_growth_cm_per_year=0.55,
        crown_ratio=0.72,
        height_coefficient=2.2,
        height_exponent=0.65,
        crown_coefficient=0.9,
        crown_exponent=0.55,
    ),
    "deciduous": GrowthProfile(
        group="deciduous",
        max_dbh_cm=150.0,
        max_height_m=42.0,
        dbh_growth_cm_per_year=0.72,
        crown_ratio=0.52,
        height_coefficient=2.4,
        height_exponent=0.55,
        crown_coefficient=1.25,
        crown_exponent=0.55,
    ),
    "unknown": GrowthProfile(
        group="unknown",
        max_dbh_cm=110.0,
        max_height_m=35.0,
        dbh_growth_cm_per_year=0.58,
        crown_ratio=0.58,
        height_coefficient=2.2,
        height_exponent=0.58,
        crown_coefficient=1.05,
        crown_exponent=0.55,
    ),
}


def species_group(name: str) -> SpeciesGroup:
    """Classify a species name into a broad growth group.

    Parameters
    ----------
    name : str
        Scientific name, common name, or source taxon string.

    Returns
    -------
    str
        ``conifer``, ``deciduous``, or ``unknown``.
    """
    text = name.strip().lower()
    if not text:
        return "unknown"
    if any(_matches_word(text, word) for word in CONIFER_WORDS):
        return "conifer"
    if any(_matches_word(text, word) for word in DECIDUOUS_WORDS):
        return "deciduous"
    return "unknown"


def _matches_word(text: str, word: str) -> bool:
    """Match a keyword as a whole word or exact phrase.

    Parameters
    ----------
    text : str
        Lower-case haystack.
    word : str
        Keyword or phrase.

    Returns
    -------
    bool
        ``True`` when the keyword occurs as a word or phrase.
    """
    if " " in word:
        return word in text
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def is_native_species(name: str) -> bool:
    """Return whether a species name matches the local native-species list.

    Parameters
    ----------
    name : str
        Scientific or common name.

    Returns
    -------
    bool
        ``True`` when the name matches a known native species or genus phrase.
    """
    text = name.strip().lower()
    if not text:
        return False
    return any(word in text for word in NATIVE_WORDS)


def profile_for(name: str) -> GrowthProfile:
    """Return the growth profile for a species name.

    Parameters
    ----------
    name : str
        Scientific or common name.

    Returns
    -------
    GrowthProfile
        The profile for the inferred species group.
    """
    return PROFILES[species_group(name)]


def estimate_height_m(dbh_cm: float, group: SpeciesGroup | str) -> float:
    """Estimate total tree height from diameter.

    Parameters
    ----------
    dbh_cm : float
        Diameter at breast height in centimetres.
    group : str
        Species group name.

    Returns
    -------
    float
        Height in metres, capped at the profile maximum.
    """
    profile = _profile(group)
    dbh = max(float(dbh_cm), 1.0)
    height = 1.3 + profile.height_coefficient * dbh**profile.height_exponent
    return float(min(height, profile.max_height_m))


def estimate_dbh_cm(height_m: float, group: SpeciesGroup | str) -> float:
    """Estimate diameter from total tree height.

    Parameters
    ----------
    height_m : float
        Height in metres.
    group : str
        Species group name.

    Returns
    -------
    float
        Diameter at breast height in centimetres, capped at the profile maximum.
    """
    profile = _profile(group)
    height = max(float(height_m), 1.4)
    dbh = ((height - 1.3) / profile.height_coefficient) ** (1.0 / profile.height_exponent)
    return float(min(max(dbh, 1.0), profile.max_dbh_cm))


def estimate_crown_width_m(dbh_cm: float, group: SpeciesGroup | str) -> float:
    """Estimate mean crown width from diameter.

    Parameters
    ----------
    dbh_cm : float
        Diameter at breast height in centimetres.
    group : str
        Species group name.

    Returns
    -------
    float
        Crown width in metres.
    """
    profile = _profile(group)
    dbh = max(float(dbh_cm), 1.0)
    return float(profile.crown_coefficient * dbh**profile.crown_exponent)


def crown_volume_m3(
    height_m: float,
    crown_width_m: float,
    crown_ratio: float = 0.5,
) -> float:
    """Estimate crown volume as an ellipsoid.

    Parameters
    ----------
    height_m : float
        Total tree height in metres.
    crown_width_m : float
        Mean crown width in metres.
    crown_ratio : float
        Live-crown ratio, 0 to 1.

    Returns
    -------
    float
        Crown volume in cubic metres.
    """
    depth = max(0.5, float(height_m) * min(max(float(crown_ratio), 0.05), 1.0))
    width = max(0.1, float(crown_width_m))
    return math.pi / 6.0 * width * width * depth


def aboveground_biomass_kg(dbh_cm: float, group: SpeciesGroup | str) -> float:
    """Estimate above-ground dry biomass with the Jenkins et al. (2003) model.

    Parameters
    ----------
    dbh_cm : float
        Diameter at breast height in centimetres.
    group : str
        Species group name.

    Returns
    -------
    float
        Above-ground dry biomass in kilograms.
    """
    dbh = max(float(dbh_cm), 1.0)
    if _profile(group).group == "conifer":
        return math.exp(-2.5356 + 2.4349 * math.log(dbh))
    return math.exp(-2.4800 + 2.4835 * math.log(dbh))


def carbon_kg(dbh_cm: float, group: SpeciesGroup | str) -> float:
    """Estimate above-ground carbon mass.

    Parameters
    ----------
    dbh_cm : float
        Diameter at breast height in centimetres.
    group : str
        Species group name.

    Returns
    -------
    float
        Carbon in kilograms, taken as half of above-ground biomass.
    """
    return 0.5 * aboveground_biomass_kg(dbh_cm, group)


def annual_dbh_increment_cm(
    dbh_cm: float,
    group: SpeciesGroup | str,
    *,
    competition: float = 1.0,
    climate: float = 1.0,
) -> float:
    """Estimate one year of diameter growth.

    Parameters
    ----------
    dbh_cm : float
        Current diameter in centimetres.
    group : str
        Species group name.
    competition : float
        Multiplier for local competition, where 1 is open-grown.
    climate : float
        Multiplier for site productivity, where 1 is the default.

    Returns
    -------
    float
        Annual diameter increment in centimetres, clamped to a plausible range.
    """
    profile = _profile(group)
    ratio = min(max(float(dbh_cm) / profile.max_dbh_cm, 0.0), 0.999)
    increment = profile.dbh_growth_cm_per_year * (1.0 - ratio**1.5)
    increment *= max(0.05, competition) * max(0.05, climate)
    return float(min(max(increment, 0.01), 1.5))


def grow_tree(tree: TreeRecord, years: int, *, competition: float = 1.0) -> TreeRecord:
    """Project one tree forward by a number of years.

    Parameters
    ----------
    tree : TreeRecord
        Tree to grow.
    years : int
        Number of annual steps.
    competition : float
        Competition multiplier passed to the increment model.

    Returns
    -------
    TreeRecord
        A new record. Missing diameter is estimated from height, and missing height is
        estimated from diameter, before growth starts.
    """
    if years <= 0 or tree.status == "removed" or tree.status == "dead":
        return tree
    group = species_group(tree.species or tree.common_name)
    dbh = tree.dbh_cm
    if dbh is None:
        dbh = estimate_dbh_cm(tree.height_m or 5.0, group)
    height = tree.height_m or estimate_height_m(dbh, group)
    crown = tree.crown_width_m or estimate_crown_width_m(dbh, group)
    ratio = tree.crown_ratio or profile_for(tree.species).crown_ratio
    for _ in range(int(years)):
        dbh = min(
            profile_for(tree.species).max_dbh_cm,
            dbh + annual_dbh_increment_cm(dbh, group, competition=competition),
        )
    height = max(height, estimate_height_m(dbh, group))
    crown = max(crown, estimate_crown_width_m(dbh, group))
    return TreeRecord(
        tree_id=tree.tree_id,
        lon=tree.lon,
        lat=tree.lat,
        species=tree.species,
        common_name=tree.common_name,
        genus=tree.genus,
        dbh_cm=round(dbh, 2),
        height_m=round(height, 2),
        crown_width_m=round(crown, 2),
        crown_ratio=ratio,
        status=tree.status,
        source=tree.source,
        source_date=tree.source_date,
        native=tree.native,
        x_m=tree.x_m,
        y_m=tree.y_m,
        elevation_m=tree.elevation_m,
        lidar_height_m=tree.lidar_height_m,
        attributes=tree.attributes,
    )


def tree_carbon_kg(tree: TreeRecord) -> float:
    """Estimate carbon for a tree record.

    Parameters
    ----------
    tree : TreeRecord
        Tree to evaluate.

    Returns
    -------
    float
        Above-ground carbon in kilograms.
    """
    if tree.dbh_cm is None:
        return 0.0
    return carbon_kg(tree.dbh_cm, species_group(tree.species or tree.common_name))


def tree_crown_volume_m3(tree: TreeRecord) -> float:
    """Estimate crown volume for a tree record.

    Parameters
    ----------
    tree : TreeRecord
        Tree to evaluate.

    Returns
    -------
    float
        Crown volume in cubic metres, or zero when height or crown width is missing.
    """
    if tree.height_m is None or tree.crown_width_m is None:
        return 0.0
    return crown_volume_m3(tree.height_m, tree.crown_width_m, tree.crown_ratio)


def _profile(group: SpeciesGroup | str) -> GrowthProfile:
    """Return a profile for a group name, falling back to ``unknown``.

    Parameters
    ----------
    group : str
        Species group name.

    Returns
    -------
    GrowthProfile
        The matching profile.
    """
    if group == "conifer":
        return PROFILES["conifer"]
    if group == "deciduous":
        return PROFILES["deciduous"]
    return PROFILES["unknown"]
