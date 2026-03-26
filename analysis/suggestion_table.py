"""
Symptom → setup suggestion lookup table.

Completely offline, no dependencies.  Each Symptom maps to an ordered list
of SuggestionEntry objects, ranked by expected impact (priority 1 = highest).

Writing style: direct, actionable, explains the *why* briefly.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from analysis.symptom_detector import Symptom, SymptomType


@dataclass(frozen=True)
class SuggestionEntry:
    title: str
    detail: str
    priority: int               # 1 = highest impact
    category: str               # "suspension" | "alignment" | "aero" | "differential" | "brakes" | "tyres"
    condition: Optional[str] = None  # optional context note, e.g. "if tyre temps are high"

    @property
    def category_icon(self) -> str:
        return {
            "suspension":   "S",
            "alignment":    "A",
            "aero":         "W",
            "differential": "D",
            "brakes":       "B",
            "tyres":        "T",
        }.get(self.category, "?")


SUGGESTIONS: dict[SymptomType, list[SuggestionEntry]] = {

    # -----------------------------------------------------------------------
    SymptomType.UNDERSTEER_ENTRY: [
        SuggestionEntry(
            title="Soften front anti-roll bar",
            detail="Reduce front ARB by 3–5 clicks. A stiffer front ARB transfers weight away from "
                   "the inside front during turn-in, reducing its grip. Softer = more front grip at entry.",
            priority=1,
            category="suspension",
        ),
        SuggestionEntry(
            title="Add front negative camber",
            detail="Increase front camber magnitude by 0.2–0.5°. As the car rolls in a corner the "
                   "outer tyre gains a more upright stance, maximising contact patch under load.",
            priority=2,
            category="alignment",
        ),
        SuggestionEntry(
            title="Soften front bump damping",
            detail="Reduce front bump damping 2–3 clicks. A stiff bump setting resists tyre "
                   "compliance over surface irregularities at turn-in, reducing mechanical grip.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Add front toe-out",
            detail="1–2 clicks of front toe-out sharpens initial turn-in response by pre-loading "
                   "the steering geometry before the wheel rolls into the corner.",
            priority=4,
            category="alignment",
        ),
        SuggestionEntry(
            title="Increase front wing / downforce",
            detail="If an aero adjustment is available, add front downforce to increase front grip "
                   "at higher speeds. Check balance — you may need to add rear downforce too.",
            priority=5,
            category="aero",
            condition="High-speed corners only",
        ),
        SuggestionEntry(
            title="Raise front ride height slightly",
            detail="A slightly higher front ride height increases front roll stiffness via geometry, "
                   "which can help in some cars. Try 2–3 mm. Monitor for aero changes.",
            priority=6,
            category="suspension",
            condition="If spring rates are already soft",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.UNDERSTEER_EXIT: [
        SuggestionEntry(
            title="Reduce differential power lock",
            detail="Lower the power-side ramp angle on the differential. A locked diff on exit "
                   "pulls the car straight, preventing it from tracking around the corner.",
            priority=1,
            category="differential",
        ),
        SuggestionEntry(
            title="Stiffen rear anti-roll bar",
            detail="Increase rear ARB 2–4 clicks to transfer more load to the rear axle on exit, "
                   "balancing the car and freeing the front to rotate.",
            priority=2,
            category="suspension",
        ),
        SuggestionEntry(
            title="Soften front springs",
            detail="Reduce front spring rate 2–3 steps to allow the front to load up more "
                   "progressively under throttle application.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Reduce front toe-in / increase toe-out",
            detail="Front toe-in causes resistance to direction change. Shifting toward neutral "
                   "or slight toe-out helps the front stay pointed through the corner exit.",
            priority=4,
            category="alignment",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.OVERSTEER_ENTRY: [
        SuggestionEntry(
            title="Stiffen rear anti-roll bar",
            detail="Increase rear ARB 3–5 clicks. The rear is rolling too freely under braking / "
                   "turn-in, causing weight to snap to the outside rear and break traction.",
            priority=1,
            category="suspension",
        ),
        SuggestionEntry(
            title="Add rear toe-in",
            detail="1–2 clicks of rear toe-in provides passive stability and resists yaw at "
                   "corner entry, reducing snap oversteer tendency.",
            priority=2,
            category="alignment",
        ),
        SuggestionEntry(
            title="Soften rear rebound damping",
            detail="Reduce rear rebound 2–3 clicks. If the rear is slow to recover from a "
                   "compression event, it can unsettle under trail-braking.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Reduce brake bias to front",
            detail="Shift brake bias 1–2% toward the front to reduce rear brake force at "
                   "corner entry. Too much rear brake + lateral load = rotation.",
            priority=4,
            category="brakes",
        ),
        SuggestionEntry(
            title="Increase rear downforce",
            detail="Add rear wing if available to plant the rear under combined braking and "
                   "lateral load. More effective at higher speeds.",
            priority=5,
            category="aero",
            condition="High-speed corners",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.OVERSTEER_EXIT: [
        SuggestionEntry(
            title="Soften rear anti-roll bar",
            detail="Reduce rear ARB 3–5 clicks. A stiff rear ARB under throttle transfers load "
                   "off the inside rear tyre, reducing drive traction and causing exit oversteer.",
            priority=1,
            category="suspension",
        ),
        SuggestionEntry(
            title="Reduce differential power ramp angle",
            detail="Lower the power-side differential ramp angle. An aggressive diff slams load "
                   "across the rear axle too abruptly, rotating the car on throttle.",
            priority=2,
            category="differential",
        ),
        SuggestionEntry(
            title="Add rear toe-in",
            detail="1–2 clicks of rear toe-in provides passive stability under acceleration. "
                   "The rear tyres resist yaw rotation when loaded.",
            priority=3,
            category="alignment",
        ),
        SuggestionEntry(
            title="Stiffen rear springs",
            detail="Increase rear spring rate 1–2 steps to reduce squat under acceleration, "
                   "which helps keep both rear tyres loaded evenly.",
            priority=4,
            category="suspension",
        ),
        SuggestionEntry(
            title="Add rear negative camber",
            detail="Increase rear camber magnitude by 0.2°. Helps the outside rear maintain "
                   "contact as the car squats and rolls under power.",
            priority=5,
            category="alignment",
            condition="If tyre temps show outer edge cooler than inner",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.TRACTION_LOSS: [
        SuggestionEntry(
            title="Soften rear anti-roll bar",
            detail="Reduce rear ARB 2–4 clicks. Reducing rear roll stiffness allows both rear "
                   "tyres to share load more evenly, improving traction out of slow corners.",
            priority=1,
            category="suspension",
        ),
        SuggestionEntry(
            title="Reduce differential preload",
            detail="Lower differential preload torque. High preload locks the rear diff too "
                   "early and causes one rear to spin under low-speed traction.",
            priority=2,
            category="differential",
        ),
        SuggestionEntry(
            title="Soften rear bump damping",
            detail="Reduce rear bump damping 2 clicks. Better tyre compliance on surface "
                   "undulations maintains contact patch and traction.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Increase rear ride height slightly",
            detail="More rear ride height increases rear roll stiffness geometrically and "
                   "can help plant the rear on corner exit.",
            priority=4,
            category="suspension",
        ),
        SuggestionEntry(
            title="Check rear tyre temperatures",
            detail="If rear tread temps are below 60 °C, tyres are not at working temperature. "
                   "Consider a longer warm-up or softer compound if available.",
            priority=5,
            category="tyres",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.BRAKE_INSTABILITY: [
        SuggestionEntry(
            title="Adjust brake bias toward front",
            detail="Shift brake bias 2–3% to the front. Rear brakes locking under trail-braking "
                   "rotates the car unpredictably. Front bias keeps the car stable.",
            priority=1,
            category="brakes",
        ),
        SuggestionEntry(
            title="Check brake duct settings",
            detail="Asymmetric brake temperatures suggest unequal cooling. Check that brake duct "
                   "settings are equal left and right, or open the hotter side's duct.",
            priority=2,
            category="brakes",
        ),
        SuggestionEntry(
            title="Increase front brake duct opening",
            detail="If front brakes are running very hot (>500 °C), open front brake ducts to "
                   "prevent fade. Fading brakes produce inconsistent lock-up behaviour.",
            priority=3,
            category="brakes",
            condition="If front brake temps are high",
        ),
        SuggestionEntry(
            title="Stiffen front rebound damping",
            detail="Increase front rebound 2 clicks. Under heavy braking, the nose dives and "
                   "rebounds — a controlled rebound keeps the geometry stable.",
            priority=4,
            category="suspension",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.TYRE_OVERHEATING: [
        SuggestionEntry(
            title="Open tyre cooling ducts",
            detail="Increase brake / tyre duct opening to improve airflow to the overheating "
                   "corners. Sustained over-temperature degrades rubber and causes graining.",
            priority=1,
            category="tyres",
        ),
        SuggestionEntry(
            title="Reduce camber on affected axle",
            detail="Excess negative camber concentrates load on the inner edge, generating "
                   "more heat than the tyre can dissipate. Reduce by 0.2–0.3°.",
            priority=2,
            category="alignment",
        ),
        SuggestionEntry(
            title="Increase tyre pressure slightly",
            detail="Higher pressure reduces flexing in the sidewall which generates heat. "
                   "Try +0.1–0.2 bar on the hot corners. Monitor for grip loss.",
            priority=3,
            category="tyres",
            condition="If tyre is already at or above target pressure",
        ),
        SuggestionEntry(
            title="Soften anti-roll bar on hot axle",
            detail="A softer ARB reduces the load on the outside tyre and distributes load "
                   "more evenly across the contact patch, lowering peak temperatures.",
            priority=4,
            category="suspension",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.TYRE_UNDERTEMP: [
        SuggestionEntry(
            title="Reduce tyre pressure on cold axle",
            detail="Lower pressure by 0.1–0.2 bar to increase sidewall flex and heat "
                   "generation. Cold tyres have much less grip than at working temperature.",
            priority=1,
            category="tyres",
        ),
        SuggestionEntry(
            title="Increase camber on cold axle",
            detail="More negative camber loads the inner edge more aggressively, generating "
                   "heat faster. Increase by 0.2–0.3° on the undertemperature wheels.",
            priority=2,
            category="alignment",
        ),
        SuggestionEntry(
            title="Stiffen anti-roll bar on cold axle",
            detail="More ARB stiffness puts more load through that axle's tyres during "
                   "cornering, helping them reach temperature sooner.",
            priority=3,
            category="suspension",
            condition="If balance allows",
        ),
        SuggestionEntry(
            title="Drive more aggressively to build heat",
            detail="On out-laps or after a safety car, weave gently and brake later to "
                   "generate heat in the cold tyres before pushing hard.",
            priority=4,
            category="tyres",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.SUSPENSION_BOTTOMING: [
        SuggestionEntry(
            title="Increase ride height on bottoming corners",
            detail="Raise the affected corner's ride height by 2–5 mm. Bottoming causes "
                   "sudden grip loss and can damage floor or diffuser components.",
            priority=1,
            category="suspension",
        ),
        SuggestionEntry(
            title="Stiffen springs on bottoming axle",
            detail="Increase spring rate 2–3 steps to reduce total suspension travel under "
                   "combined aero load and road bumps.",
            priority=2,
            category="suspension",
        ),
        SuggestionEntry(
            title="Increase bump damping",
            detail="Raise bump damping 2–3 clicks to slow the initial compression rate "
                   "over kerbs or compressions, giving the spring time to react.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Check bump stop gap",
            detail="If bump stops are accessible in setup, increase the gap or use a softer "
                   "bump stop to prevent abrupt contact with the chassis.",
            priority=4,
            category="suspension",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.WHEEL_LOCK: [
        SuggestionEntry(
            title="Shift brake bias toward rear",
            detail="Move brake bias 2–3% toward the rear. Front lock-up means the fronts "
                   "are doing too much work — redistributing reduces peak front brake force.",
            priority=1,
            category="brakes",
            condition="If front wheels are locking",
        ),
        SuggestionEntry(
            title="Reduce brake pressure / master cylinder",
            detail="Lower overall brake pressure if adjustable. Locking consistently "
                   "means brake force is exceeding available grip, not a balance issue.",
            priority=2,
            category="brakes",
        ),
        SuggestionEntry(
            title="Open brake ducts on locking axle",
            detail="If brakes are overheating they fade and then bite unpredictably, "
                   "causing lock-up. Opening ducts keeps discs in their working range.",
            priority=3,
            category="brakes",
            condition="If brake temps are high on locking wheels",
        ),
        SuggestionEntry(
            title="Stiffen suspension on locking axle",
            detail="Softer suspension allows more weight transfer under braking, "
                   "overloading one axle. A stiffer setup keeps load more consistent.",
            priority=4,
            category="suspension",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.ABS_INSUFFICIENT: [
        SuggestionEntry(
            title="Increase ABS setting",
            detail="ABS is active but wheels are still locking. Increase the ABS setting "
                   "by 1–2 steps so the system intervenes earlier before full lock occurs.",
            priority=1,
            category="brakes",
        ),
        SuggestionEntry(
            title="Shift brake bias toward front",
            detail="If rear wheels are locking despite ABS, the rear is overbraked relative "
                   "to front grip. Move bias 1–2% forward to reduce rear lock tendency.",
            priority=2,
            category="brakes",
            condition="If rear wheels are locking",
        ),
        SuggestionEntry(
            title="Check brake temperatures",
            detail="Overheated brakes fade and then bite unevenly, overwhelming ABS. "
                   "Open brake ducts on the locking axle to keep temps in range.",
            priority=3,
            category="brakes",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.ABS_OVER_INTERVENTION: [
        SuggestionEntry(
            title="Reduce ABS setting",
            detail="ABS is cutting in at moderate brake pressure on a straight, suggesting "
                   "it is set too aggressively. Reduce by 1–2 steps for better trail-braking "
                   "feel and less brake force loss.",
            priority=1,
            category="brakes",
        ),
        SuggestionEntry(
            title="Check tyre pressures",
            detail="Under-inflated tyres have a larger contact patch and generate more slip "
                   "per unit brake force, triggering ABS prematurely. Check pressures are "
                   "at target.",
            priority=2,
            category="tyres",
        ),
        SuggestionEntry(
            title="Check cold tyre temperatures",
            detail="Cold tyres have much lower grip, causing ABS to activate earlier than "
                   "normal. If this occurs at the start of a stint, allow more warm-up time.",
            priority=3,
            category="tyres",
            condition="Early in stint or after safety car",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.OFF_TRACK: [
        SuggestionEntry(
            title="No setup change needed",
            detail="Car is off the racing surface. Setup suggestions are paused until "
                   "back on track. Tyre temperatures and grip readings are unreliable.",
            priority=1,
            category="tyres",
        ),
    ],
}


def get_suggestions(symptom: Symptom, max_count: int = 3) -> list[SuggestionEntry]:
    """Return the top N suggestions for a given symptom, sorted by priority."""
    entries = SUGGESTIONS.get(symptom.symptom_type, [])
    return sorted(entries, key=lambda e: e.priority)[:max_count]


def get_all_suggestions(symptoms: list[Symptom], max_per_symptom: int = 3) -> dict[Symptom, list[SuggestionEntry]]:
    """Return suggestions for a list of symptoms, keyed by Symptom object."""
    return {s: get_suggestions(s, max_per_symptom) for s in symptoms}
