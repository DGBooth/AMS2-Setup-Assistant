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
            title="Soften front slow bump",
            detail="Reduce front slow bump 2–3 clicks. Slow bump controls compression during "
                   "braking and turning; a stiff setting resists tyre compliance at turn-in, "
                   "reducing mechanical grip over surface irregularities.",
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
            title="Increase clutch LSD power ramp",
            detail="Raise the on-power ramp setting. In AMS2, a higher power ramp value increases "
                   "the locking effect under throttle, helping the car track through the corner "
                   "exit instead of pushing wide. Increase in small steps and re-test.",
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
            title="Soften rear slow rebound",
            detail="Reduce rear slow rebound 2–3 clicks. Slow rebound controls decompression "
                   "during braking and turning; if the rear recovers too slowly from compression "
                   "under trail-braking it stays jacked up and can snap loose at entry.",
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
        SuggestionEntry(
            title="Increase engine braking",
            detail="A low engine braking value produces an abrupt power cut on lift-off that "
                   "unsettles the rear. Raise it to smooth the deceleration rate and stabilise "
                   "the car during trail-braking. Note: AMS2 has a bug where values above 5 "
                   "can blow the engine on some cars — keep it at 5 maximum.",
            priority=6,
            category="differential",
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
            title="Reduce clutch LSD power ramp",
            detail="Lower the on-power ramp setting. In AMS2, a higher power ramp value increases "
                   "the locking effect and oversteer tendency on exit — reducing it allows the rear "
                   "wheels to differentiate more freely under throttle, taming snap oversteer.",
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
            title="Reduce clutch LSD preload",
            detail="Lower clutch LSD preload torque. In slow corners, high preload forces both "
                   "rear wheels to spin at equal speed; the geometry requires the outer wheel to "
                   "travel faster, so the diff fights the corner and scrubs traction from the "
                   "inside rear. Less preload lets the wheels differentiate naturally.",
            priority=2,
            category="differential",
        ),
        SuggestionEntry(
            title="Soften rear slow bump",
            detail="Reduce rear slow bump 2 clicks. Slow bump controls compression under "
                   "acceleration; better tyre compliance on surface undulations maintains "
                   "the rear contact patch and traction.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Increase rear ride height slightly",
            detail="More rear ride height increases rear roll stiffness geometrically and "
                   "can help plant the rear on corner exit. In AMS2 the rear underfloor has a "
                   "sweet spot range for downforce — adjust in small increments to stay within it.",
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
            title="Check front/rear duct opening settings",
            detail="Asymmetric brake temperatures suggest unequal cooling. Check that front and "
                   "rear duct opening settings are equal left and right, or open the hotter side.",
            priority=2,
            category="brakes",
        ),
        SuggestionEntry(
            title="Increase front duct opening",
            detail="If front brakes are running very hot (>500 °C), increase the front duct "
                   "opening to prevent fade. Fading brakes produce inconsistent lock-up behaviour.",
            priority=3,
            category="brakes",
            condition="If front brake temps are high",
        ),
        SuggestionEntry(
            title="Stiffen front slow rebound",
            detail="Increase front slow rebound 2 clicks. Slow rebound controls decompression "
                   "during braking; a controlled recovery after nose dive keeps the geometry "
                   "stable and prevents the front from snapping back mid-corner.",
            priority=4,
            category="suspension",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.TYRE_OVERHEATING: [
        SuggestionEntry(
            title="Increase duct opening on hot axle",
            detail="Increase the front or rear duct opening (whichever axle is overheating) to "
                   "improve airflow. Sustained over-temperature degrades rubber and causes graining.",
            priority=1,
            category="tyres",
        ),
        SuggestionEntry(
            title="Reduce camber on affected axle",
            detail="Excess negative camber concentrates load on the inner edge, generating "
                   "more heat than the tyre can dissipate. Reduce by 0.2–0.3°. In AMS2, "
                   "target inner edge ~7°C hotter than outer (front) or ~3–5°C (rear); "
                   "if the inner is much hotter, camber is the first adjustment.",
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
                   "heat faster. Increase by 0.2–0.3° on the undertemperature wheels. In AMS2 "
                   "target inner edge ~7°C hotter than outer (front) or ~3–5°C (rear) — if the "
                   "spread is smaller than that, more camber will help reach temperature.",
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
                   "sudden grip loss and can damage floor or diffuser components. In AMS2 the "
                   "rear underfloor has a downforce sweet spot — raise cautiously and check "
                   "balance after each change.",
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
            title="Increase fast bump on bottoming axle",
            detail="Raise fast bump 2–3 clicks. Fast bump resists rapid compression over kerbs "
                   "and sudden compressions, slowing the initial travel rate and giving the spring "
                   "time to react. Use slow bump instead if bottoming occurs on gradual undulations.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Adjust bumpstop gap",
            detail="Increase the bumpstop gap to delay when the bumpstop engages, or fit a "
                   "softer bumpstop to prevent the abrupt chassis contact that causes sudden grip loss.",
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
            title="Increase duct opening on locking axle",
            detail="If brakes are overheating they fade and then bite unpredictably, causing "
                   "lock-up. Increase the front or rear duct opening to keep discs in their "
                   "working range.",
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
            title="Increase anti-lock brakes setting",
            detail="ABS is active but wheels are still locking. Increase the anti-lock brakes "
                   "setting by 1–2 steps so the system intervenes earlier before full lock occurs.",
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
                   "Increase the front or rear duct opening on the locking axle to keep "
                   "brake temps in range.",
            priority=3,
            category="brakes",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.ABS_OVER_INTERVENTION: [
        SuggestionEntry(
            title="Reduce anti-lock brakes setting",
            detail="ABS is cutting in at moderate brake pressure on a straight, suggesting "
                   "it is set too aggressively. Reduce the anti-lock brakes setting by 1–2 "
                   "steps for better trail-braking feel and less brake force loss.",
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

    # -----------------------------------------------------------------------
    SymptomType.LATE_BRAKING: [
        SuggestionEntry(
            title="Move brake bias rearward",
            detail="Shift brake balance 1–2% toward the rear. Heavy simultaneous brake "
                   "and steering locks the front tyres and pushes the car wide. A rear "
                   "bias reduces peak front brake torque, allowing the fronts to steer "
                   "while still decelerating.",
            priority=1,
            category="brakes",
        ),
        SuggestionEntry(
            title="Soften front slow bump damping",
            detail="Reduce front slow bump 2–3 clicks. When braking and turning "
                   "simultaneously, the front suspension must absorb both longitudinal "
                   "and lateral load spikes. Softer slow bump lets the tyre comply with "
                   "the road rather than skating across it.",
            priority=2,
            category="suspension",
        ),
        SuggestionEntry(
            title="Soften front anti-roll bar",
            detail="Reduce front ARB 2–3 clicks. A stiff front ARB resists body roll, "
                   "but under combined braking and cornering load it also reduces how much "
                   "weight the outer front can carry, causing the tyre to exceed its grip "
                   "limit sooner.",
            priority=3,
            category="suspension",
        ),
        SuggestionEntry(
            title="Check front brake duct sizing",
            detail="Ensure front brake ducts are appropriate for the circuit. Sustained "
                   "hard braking into corners rapidly heats the brakes; overheated "
                   "brakes fade and produce an inconsistent pedal, making it harder to "
                   "modulate pressure accurately under cornering load.",
            priority=4,
            category="brakes",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.EARLY_THROTTLE: [
        SuggestionEntry(
            title="Reduce LSD power ramp angle",
            detail="Lower the on-power ramp (lock) setting on the differential. Applying "
                   "throttle hard before the apex asks the diff to lock up while the car "
                   "is still generating high lateral G. A high power ramp at this point "
                   "snaps the rear sideways — reducing it gives a more progressive "
                   "rotation on exit.",
            priority=1,
            category="differential",
        ),
        SuggestionEntry(
            title="Stiffen rear anti-roll bar",
            detail="Increase rear ARB 2–3 clicks. A softer rear ARB allows the rear to "
                   "roll and unload the inside rear tyre when throttle is applied "
                   "mid-corner. A stiffer setting keeps the rear platform flatter, "
                   "resisting the rotation caused by early power application.",
            priority=2,
            category="suspension",
        ),
        SuggestionEntry(
            title="Check rear tyre pressures",
            detail="Verify rear tyre pressures are within the recommended range. High "
                   "pressures reduce the contact patch and make the rear more sensitive "
                   "to load changes — early throttle on an overinflated rear tyre "
                   "significantly increases the snap oversteer risk.",
            priority=3,
            category="tyres",
        ),
        SuggestionEntry(
            title="Add rear negative camber",
            detail="Increase rear camber magnitude by 0.2–0.3°. As the car accelerates "
                   "and the body squats, more camber keeps the rear tyre's contact patch "
                   "better loaded under the combined lateral and longitudinal forces of "
                   "an early throttle application.",
            priority=4,
            category="alignment",
        ),
    ],

    # -----------------------------------------------------------------------
    SymptomType.SLOW_CORNER_EXIT: [
        SuggestionEntry(
            title="Reduce LSD power ramp to encourage earlier throttle",
            detail="Lower the on-power differential lock setting. If exit oversteer or "
                   "snap is causing the driver to hesitate on throttle application, a "
                   "less aggressive power ramp makes the exit more predictable and "
                   "encourages earlier, more confident acceleration.",
            priority=1,
            category="differential",
        ),
        SuggestionEntry(
            title="Soften rear anti-roll bar",
            detail="Reduce rear ARB 2–3 clicks. A stiff rear ARB can cause the rear to "
                   "snap abruptly when the car is unwinding from a corner and throttle "
                   "is applied. A softer setting produces a more gradual, predictable "
                   "weight transfer that encourages the driver to open the throttle "
                   "earlier.",
            priority=2,
            category="suspension",
        ),
        SuggestionEntry(
            title="Check rear tyre temperatures",
            detail="Cold or inconsistently heated rear tyres feel skittish under "
                   "acceleration, causing drivers to back off instinctively. Verify "
                   "rear tread temperatures are in the working window (60–105 °C) by "
                   "the time you reach corner exits.",
            priority=3,
            category="tyres",
        ),
        SuggestionEntry(
            title="Increase rear ride height slightly",
            detail="Raise rear ride height 2–3 mm. If the rear is bottoming or the "
                   "suspension is topping out under acceleration squat, it creates "
                   "an unsettled feeling that deters early throttle. More rear travel "
                   "gives the suspension room to absorb the squat progressively.",
            priority=4,
            category="suspension",
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
