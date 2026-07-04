#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Author the free-response questions (FRQ) for the topical practice tests.

Single source of truth for the hand-authored FRQ content. For each test it sets
the `free_response_questions` array (replacing any existing one, so it is
idempotent and re-runnable) into BOTH copies of the JSON — the resources/
source-of-truth and the ts/ shipped copy — keeping them byte-identical, and
validates the invariant `max_points == sum(rubric points)`.

Counts follow 20% x (AAMC content-% x section question count): ~13 FRQ per
science test, ~11 for CARS (~89 total). Content is original and grounded in
standard MCAT material (rubrics reference the correct-answer content; questions
are not copied from any source). `reviewed:false` until a human/SME pass.

Run:  out/pyenv/bin/python tools/build_frq.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "resources" / "practice_tests"
TS = ROOT / "ts" / "routes" / "practice-tests" / "tests"

Crit = tuple  # (description, points, [required_concepts], [disqualifiers])


def frq(qid: str, prompt: str, tag: str, crits: list, reference: str) -> dict:
    rubric = [
        {
            "id": f"c{i + 1}",
            "description": d,
            "points": p,
            "required_concepts": req,
            "disqualifiers": dis,
        }
        for i, (d, p, req, dis) in enumerate(crits)
    ]
    return {
        "type": "free_response",
        "id": qid,
        "prompt": prompt,
        "max_points": sum(c["points"] for c in rubric),
        "rubric": rubric,
        "reference_answer": reference,
        "topic_tags": [tag],
        "ground_truth_ref": "standard MCAT content - original framing",
        "figure": None,
        "qa": {
            "single_defensible_answer": True,
            "original_not_copied": True,
            "reviewed": False,
        },
    }


# ---------------------------------------------------------------------------
# bio-biochem-1  (biology 8, biochemistry 3, gen-chem 1, orgo 1 = 13)
# ---------------------------------------------------------------------------
BIO_BIOCHEM_1 = [
    frq(
        "bio-biochem-1-frq1",
        "Glycogen has α-1,4 linkages along its chains and α-1,6 linkages at branch "
        "points. Explain how the branched structure lets a cell mobilize glucose "
        "rapidly. Name the enzyme that releases glucose units and where it acts.",
        "aamc::bio-biochem::carbohydrates",
        [
            (
                "States that branching creates many nonreducing ends.",
                2,
                [
                    "branching produces many/multiple nonreducing ends",
                    "more ends than an unbranched chain",
                ],
                [
                    "claims branching makes glycogen insoluble",
                    "claims branching protects it from breakdown",
                ],
            ),
            (
                "Links the many ends to glycogen phosphorylase acting at nonreducing ends for rapid release.",
                2,
                [
                    "glycogen phosphorylase",
                    "acts at nonreducing ends",
                    "many ends allow simultaneous/rapid release",
                ],
                [
                    "says phosphorylase acts at the reducing end",
                    "names debranching enzyme as the main mechanism",
                    "says hexokinase or amylase releases the units",
                ],
            ),
        ],
        "Branching produces many nonreducing ends; glycogen phosphorylase cleaves "
        "glucose-1-phosphate only from nonreducing ends, so many ends let many enzymes "
        "act at once, giving rapid mobilization.",
    ),
    frq(
        "bio-biochem-1-frq2",
        "A competitive inhibitor is added to a Michaelis-Menten enzyme reaction. "
        "Describe the effect on apparent Km and on Vmax, and explain in one sentence "
        "why Vmax is affected the way it is.",
        "aamc::bio-biochem::enzyme-kinetics",
        [
            (
                "States a competitive inhibitor increases the apparent Km.",
                2,
                ["apparent Km increases / higher Km", "competes for the active site"],
                [
                    "says Km decreases",
                    "says the inhibitor binds an allosteric/non-active site",
                ],
            ),
            (
                "States Vmax is unchanged because high substrate outcompetes the inhibitor.",
                2,
                ["Vmax unchanged", "high/excess substrate outcompetes the inhibitor"],
                ["says Vmax decreases", "says Vmax increases"],
            ),
        ],
        "A competitive inhibitor raises apparent Km because it competes with substrate "
        "for the active site; Vmax is unchanged because enough substrate outcompetes "
        "the inhibitor and still saturates the enzyme.",
    ),
    frq(
        "bio-biochem-1-frq3",
        "The primary structure of the enzyme ribonuclease is sufficient to specify its "
        "folded, active shape. Explain what this means about how proteins fold and "
        "identify the level of structure that the amino acid sequence directly determines.",
        "aamc::bio-biochem::protein-structure",
        [
            (
                "States the amino acid sequence (primary structure) determines the higher-order folding.",
                2,
                [
                    "primary structure / amino acid sequence determines folding",
                    "sequence dictates tertiary/3D structure",
                ],
                [
                    "says folding is set by chaperones independent of sequence",
                    "says the DNA directly folds the protein",
                ],
            ),
            (
                "Explains folding is driven by the side chains / interactions (e.g. hydrophobic effect) of that sequence.",
                2,
                [
                    "side-chain interactions / hydrophobic interactions drive folding",
                    "R-groups determine the fold",
                ],
                [
                    "says peptide bonds alone determine the 3D fold",
                    "attributes folding only to disulfide bonds",
                ],
            ),
        ],
        "Because denatured ribonuclease refolds to its active form once denaturants are "
        "removed, the amino acid sequence (primary structure) contains all the "
        "information needed to specify the tertiary structure; folding is driven by the "
        "side-chain interactions (notably the hydrophobic effect) of that sequence.",
    ),
    frq(
        "bio-biochem-1-frq4",
        "Trace the net ATP yield of glycolysis for one glucose molecule, distinguishing "
        "the ATP invested from the ATP produced. State the net gain and name the "
        "3-carbon product.",
        "aamc::bio-biochem::glycolysis",
        [
            (
                "Accounts for 2 ATP invested and 4 ATP produced (net 2 ATP).",
                2,
                ["2 ATP invested", "4 ATP produced", "net 2 ATP"],
                [
                    "says net 4 ATP",
                    "says net 36/38 ATP for glycolysis alone",
                    "says no ATP is invested",
                ],
            ),
            (
                "Identifies pyruvate as the 3-carbon end product (and 2 NADH formed).",
                2,
                ["pyruvate", "two pyruvate / 3-carbon product", "2 NADH"],
                [
                    "says the product is lactate under aerobic conditions",
                    "says the product is acetyl-CoA",
                ],
            ),
        ],
        "Glycolysis invests 2 ATP in the early steps and produces 4 ATP later, for a net "
        "gain of 2 ATP (plus 2 NADH). Each glucose yields two molecules of the 3-carbon "
        "product pyruvate.",
    ),
    frq(
        "bio-biochem-1-frq5",
        "During the rising phase of a neuronal action potential, which ion moves and in "
        "which direction, and what channel is responsible? Explain what restores the "
        "resting potential during repolarization.",
        "aamc::bio-biochem::neurophysiology",
        [
            (
                "Rising phase = Na+ influx through voltage-gated Na+ channels (depolarization).",
                2,
                [
                    "Na+ enters/influx",
                    "voltage-gated sodium channels",
                    "depolarization",
                ],
                [
                    "says K+ causes depolarization",
                    "says Na+ leaves the cell during the rising phase",
                ],
            ),
            (
                "Repolarization = K+ efflux through voltage-gated K+ channels.",
                2,
                [
                    "K+ leaves/efflux",
                    "voltage-gated potassium channels",
                    "repolarization",
                ],
                ["says Cl- influx repolarizes", "says Na+ efflux repolarizes"],
            ),
        ],
        "The rising phase is Na+ rushing in through voltage-gated Na+ channels, "
        "depolarizing the membrane. Repolarization occurs as voltage-gated K+ channels "
        "open and K+ flows out, restoring the negative resting potential.",
    ),
    frq(
        "bio-biochem-1-frq6",
        "Contrast the humoral and cell-mediated arms of adaptive immunity: name the "
        "principal lymphocyte of each and the main way each eliminates a threat.",
        "aamc::bio-biochem::immunology",
        [
            (
                "Humoral = B cells producing antibodies against extracellular pathogens.",
                2,
                [
                    "B cells / B lymphocytes",
                    "antibodies",
                    "humoral targets extracellular pathogens/toxins",
                ],
                [
                    "says T cells drive humoral immunity",
                    "says humoral immunity kills infected cells directly",
                ],
            ),
            (
                "Cell-mediated = cytotoxic T cells killing infected/abnormal cells.",
                2,
                [
                    "cytotoxic T cells / T lymphocytes",
                    "kill infected or abnormal cells",
                ],
                [
                    "says B cells are the effectors of cell-mediated immunity",
                    "says cell-mediated immunity works by secreting antibodies",
                ],
            ),
        ],
        "Humoral immunity uses B cells, which secrete antibodies that target "
        "extracellular pathogens and toxins. Cell-mediated immunity uses T cells "
        "(notably cytotoxic T cells) that directly kill virus-infected or abnormal cells.",
    ),
    frq(
        "bio-biochem-1-frq7",
        "Hemoglobin's O2-binding curve is sigmoidal while myoglobin's is hyperbolic. "
        "Explain what property of hemoglobin produces the sigmoidal shape and why it is "
        "advantageous for O2 delivery to tissues.",
        "aamc::bio-biochem::cardiovascular",
        [
            (
                "Attributes the sigmoidal curve to cooperative binding among hemoglobin's subunits.",
                2,
                [
                    "cooperativity / cooperative binding",
                    "multiple subunits",
                    "binding of O2 increases affinity of others",
                ],
                [
                    "says myoglobin is cooperative",
                    "says the shape is due to a single binding site",
                ],
            ),
            (
                "Explains cooperativity aids delivery: high loading in lungs, ready release in tissues.",
                2,
                [
                    "loads O2 at high pO2 (lungs)",
                    "releases O2 at low pO2 (tissues)",
                    "efficient unloading",
                ],
                [
                    "says hemoglobin cannot release O2 in tissues",
                    "says it binds O2 equally at all pressures",
                ],
            ),
        ],
        "Hemoglobin has four subunits that bind O2 cooperatively—each bound O2 raises the "
        "affinity of the others—producing a sigmoidal curve. This lets hemoglobin load "
        "O2 fully in the high-pO2 lungs yet release it readily in low-pO2 tissues.",
    ),
    frq(
        "bio-biochem-1-frq8",
        "Blood glucose rises after a meal. Name the pancreatic hormone released, the "
        "cells that release it, and describe one action that lowers blood glucose. "
        "Explain how this is an example of negative feedback.",
        "aamc::bio-biochem::endocrine",
        [
            (
                "Identifies insulin from pancreatic beta cells and a glucose-lowering action.",
                2,
                [
                    "insulin",
                    "beta cells",
                    "promotes glucose uptake / glycogen synthesis",
                ],
                [
                    "says glucagon lowers blood glucose",
                    "says alpha cells release insulin",
                ],
            ),
            (
                "Explains negative feedback: the response reduces the original stimulus (high glucose).",
                2,
                [
                    "negative feedback",
                    "the response lowers glucose back toward set point / opposes the stimulus",
                ],
                [
                    "calls it positive feedback",
                    "says feedback amplifies the rise in glucose",
                ],
            ),
        ],
        "High blood glucose triggers pancreatic beta cells to release insulin, which "
        "promotes glucose uptake and glycogen synthesis, lowering blood glucose. Because "
        "the response counteracts the initial rise, returning glucose toward its set "
        "point, it is negative feedback.",
    ),
    frq(
        "bio-biochem-1-frq9",
        "In oxidative phosphorylation, the electron transport chain does not make most "
        "ATP directly. Explain how electron transport is coupled to ATP synthesis, "
        "naming the gradient involved and the enzyme that makes ATP.",
        "aamc::bio-biochem::oxidative-phosphorylation",
        [
            (
                "States the ETC pumps protons, creating a proton (H+) electrochemical gradient across the inner membrane.",
                2,
                [
                    "proton/H+ gradient",
                    "protons pumped across the inner mitochondrial membrane",
                    "electrochemical gradient",
                ],
                [
                    "says the ETC pumps electrons into the matrix to store energy",
                    "says ATP is made directly by the ETC complexes",
                ],
            ),
            (
                "States ATP synthase uses the gradient (chemiosmosis) to phosphorylate ADP.",
                2,
                [
                    "ATP synthase",
                    "protons flow back down the gradient",
                    "chemiosmosis / drives ATP synthesis",
                ],
                [
                    "says substrate-level phosphorylation makes this ATP",
                    "says oxygen directly phosphorylates ADP",
                ],
            ),
        ],
        "The electron transport chain uses electron energy to pump protons across the "
        "inner mitochondrial membrane, building an electrochemical H+ gradient. Protons "
        "then flow back through ATP synthase (chemiosmosis), which uses that energy to "
        "phosphorylate ADP to ATP.",
    ),
    frq(
        "bio-biochem-1-frq10",
        "Two phenotypically normal parents have a child with an autosomal recessive "
        "disorder. State the parents' genotypes and the probability their next child is "
        "affected. Briefly justify using a Punnett-square reasoning.",
        "aamc::bio-biochem::genetics",
        [
            (
                "States both parents are heterozygous carriers (Aa x Aa).",
                2,
                ["both parents heterozygous / carriers", "Aa x Aa"],
                [
                    "says a parent is homozygous recessive (aa)",
                    "says the trait must be dominant",
                ],
            ),
            (
                "Gives 1/4 (25%) affected and ties it to the Aa x Aa cross.",
                2,
                ["1/4 or 25% affected", "aa offspring from Aa x Aa"],
                ["says 1/2 affected", "says 3/4 affected", "says 0 chance affected"],
            ),
        ],
        "Since both parents are unaffected but have an affected child, both must be "
        "heterozygous carriers (Aa × Aa). That cross yields 1/4 aa, so each child has a "
        "25% chance of being affected.",
    ),
    frq(
        "bio-biochem-1-frq11",
        "Facilitated diffusion and primary active transport both move solutes across a "
        "membrane using proteins. Contrast them with respect to the direction relative "
        "to the concentration gradient and the requirement for ATP.",
        "aamc::bio-biochem::membrane-transport",
        [
            (
                "Facilitated diffusion: down the gradient, no ATP (passive).",
                2,
                ["down the concentration gradient", "no ATP / passive"],
                [
                    "says facilitated diffusion requires ATP",
                    "says it moves solute up the gradient",
                ],
            ),
            (
                "Primary active transport: against the gradient, requires ATP.",
                2,
                ["against/up the concentration gradient", "requires ATP directly"],
                [
                    "says active transport goes down the gradient",
                    "says active transport needs no energy",
                ],
            ),
        ],
        "Facilitated diffusion moves a solute down its concentration gradient through a "
        "protein with no energy input (passive). Primary active transport moves a solute "
        "against its gradient and consumes ATP directly to do so.",
    ),
    frq(
        "bio-biochem-1-frq12",
        "A buffer resists pH change. For a weak acid/conjugate-base buffer, explain what "
        "happens when a small amount of strong acid is added, and state (in words) the "
        "relationship that sets the buffer's pH.",
        "aamc::bio-biochem::acid-base",
        [
            (
                "Explains the conjugate base neutralizes added strong acid (H+), limiting pH change.",
                2,
                [
                    "conjugate base neutralizes added H+/strong acid",
                    "converts strong acid to weak acid",
                ],
                [
                    "says the weak acid neutralizes added acid",
                    "says the buffer adds H+ to solution",
                ],
            ),
            (
                "States pH depends on pKa and the base:acid ratio (Henderson-Hasselbalch, in words).",
                2,
                [
                    "pH set by pKa and ratio of conjugate base to acid",
                    "Henderson-Hasselbalch relationship",
                ],
                [
                    "says pH depends only on total concentration",
                    "says pH equals pKa regardless of ratio",
                ],
            ),
        ],
        "Added strong acid (H+) is consumed by the buffer's conjugate base, converting it "
        "to the weak acid, so pH barely changes. The buffer's pH is set by the acid's pKa "
        "plus the log of the conjugate-base-to-weak-acid ratio (Henderson-Hasselbalch).",
    ),
    frq(
        "bio-biochem-1-frq13",
        "Define enantiomers and diastereomers for a molecule with two stereocenters, and "
        "state how each pair differs in physical properties such as melting point.",
        "aamc::bio-biochem::stereochemistry",
        [
            (
                "Enantiomers: nonsuperimposable mirror images (all stereocenters inverted); identical physical properties (except chirality).",
                2,
                [
                    "enantiomers are nonsuperimposable mirror images",
                    "same/identical physical properties (e.g. melting point)",
                    "differ in interaction with plane-polarized light/chiral environments",
                ],
                [
                    "says enantiomers have different melting points",
                    "says enantiomers are the same compound",
                ],
            ),
            (
                "Diastereomers: stereoisomers that are NOT mirror images (some but not all centers differ); different physical properties.",
                2,
                [
                    "diastereomers are non-mirror-image stereoisomers",
                    "differ at some but not all stereocenters",
                    "different physical properties / different melting points",
                ],
                [
                    "says diastereomers are mirror images",
                    "says diastereomers have identical physical properties",
                ],
            ),
        ],
        "Enantiomers are nonsuperimposable mirror images (every stereocenter inverted); "
        "they share identical physical properties like melting point and differ only in "
        "chiral environments and the rotation of plane-polarized light. Diastereomers are "
        "stereoisomers that are not mirror images (differing at some but not all "
        "stereocenters) and have different physical properties, including melting point.",
    ),
]

# ---------------------------------------------------------------------------
# bio-biochem-2  (biology 8, biochemistry 3, gen-chem 1, orgo 1 = 13)
# ---------------------------------------------------------------------------
BIO_BIOCHEM_2 = [
    frq(
        "bio-biochem-2-frq1",
        "Explain how the loop of Henle and the countercurrent multiplier let the kidney "
        "produce urine more concentrated than blood plasma. Name the region where water "
        "is reabsorbed and what makes it possible.",
        "aamc::bio-biochem::renal",
        [
            (
                "Describes the countercurrent multiplier building a medullary osmotic gradient (hypertonic interstitium).",
                2,
                [
                    "countercurrent multiplier",
                    "hypertonic/high-solute medullary interstitium",
                    "descending vs ascending limb differ in permeability",
                ],
                [
                    "says the loop of Henle secretes urine directly",
                    "says the gradient is highest in the cortex",
                ],
            ),
            (
                "States water is reabsorbed passively down the gradient (descending limb / collecting duct via ADH).",
                2,
                [
                    "water reabsorbed in descending limb / collecting duct",
                    "water follows the osmotic gradient",
                    "ADH increases water permeability",
                ],
                [
                    "says the ascending limb is water-permeable",
                    "says active pumping of water concentrates urine",
                ],
            ),
        ],
        "The ascending limb pumps out solute to build a hypertonic medullary gradient "
        "(countercurrent multiplier). Water then leaves the water-permeable descending "
        "limb and the collecting duct (ADH-regulated) passively down that gradient, "
        "concentrating the urine.",
    ),
    frq(
        "bio-biochem-2-frq2",
        "During strenuous exercise, both the rate and depth of breathing increase. "
        "Identify the primary chemical stimulus the body monitors to drive this and "
        "explain how it changes with exercise.",
        "aamc::bio-biochem::respiratory",
        [
            (
                "Identifies rising CO2 (and resulting drop in blood pH) as the primary drive.",
                2,
                [
                    "increased CO2 / PCO2",
                    "decreased pH / more acidic blood",
                    "chemoreceptors detect it",
                ],
                [
                    "says low O2 is the primary drive under normal conditions",
                    "says rising pH drives breathing",
                ],
            ),
            (
                "Links it to increased ventilation to expel CO2 and restore pH.",
                2,
                [
                    "increased ventilation expels CO2",
                    "restores/raises pH toward normal",
                ],
                [
                    "says ventilation increases to retain CO2",
                    "says the response lowers pH further",
                ],
            ),
        ],
        "Exercise raises blood CO2, which lowers blood pH; central and peripheral "
        "chemoreceptors sense this (CO2/pH is the primary drive, not O2) and increase "
        "ventilation to blow off CO2 and bring pH back toward normal.",
    ),
    frq(
        "bio-biochem-2-frq3",
        "A neuron releases acetylcholine at a synapse. Describe how the signal crosses "
        "the synaptic cleft and how the signal is terminated so the postsynaptic neuron "
        "can reset.",
        "aamc::bio-biochem::neurophysiology",
        [
            (
                "Neurotransmitter diffuses across the cleft and binds postsynaptic receptors.",
                2,
                [
                    "acetylcholine diffuses across the synaptic cleft",
                    "binds postsynaptic receptors",
                    "triggers postsynaptic potential",
                ],
                [
                    "says the action potential jumps the cleft electrically",
                    "says ACh is reabsorbed before binding receptors",
                ],
            ),
            (
                "Signal terminated by acetylcholinesterase degrading ACh (and/or reuptake).",
                2,
                [
                    "acetylcholinesterase breaks down ACh",
                    "clears neurotransmitter from the cleft",
                ],
                [
                    "says the neurotransmitter is destroyed by the postsynaptic receptor",
                    "says the signal ends when the axon repolarizes only",
                ],
            ),
        ],
        "Acetylcholine diffuses across the cleft and binds receptors on the postsynaptic "
        "membrane, generating a postsynaptic potential. Acetylcholinesterase then "
        "hydrolyzes ACh in the cleft, terminating the signal so the synapse can reset.",
    ),
    frq(
        "bio-biochem-2-frq4",
        "Blood osmolarity rises (dehydration). Name the hormone released, where it acts "
        "in the kidney, and its effect on water. Explain how this is negative feedback.",
        "aamc::bio-biochem::endocrine",
        [
            (
                "ADH (vasopressin) increases water reabsorption in the collecting duct.",
                2,
                [
                    "ADH / vasopressin",
                    "acts on the collecting duct",
                    "increases water reabsorption",
                ],
                [
                    "says aldosterone is the primary response to high osmolarity",
                    "says ADH increases water excretion",
                ],
            ),
            (
                "Explains negative feedback: reabsorbing water lowers osmolarity back toward set point.",
                2,
                [
                    "negative feedback",
                    "water retention lowers osmolarity / opposes the stimulus",
                ],
                [
                    "calls it positive feedback",
                    "says the response raises osmolarity further",
                ],
            ),
        ],
        "High osmolarity triggers ADH release; ADH makes the collecting duct more "
        "water-permeable, increasing water reabsorption. Retaining water lowers blood "
        "osmolarity back toward its set point, so it is negative feedback.",
    ),
    frq(
        "bio-biochem-2-frq5",
        "In the bacterial lac operon, lactose is present but glucose is absent. Explain "
        "why the operon is strongly transcribed, referencing both the repressor and the "
        "role of cAMP/CAP.",
        "aamc::bio-biochem::microbiology",
        [
            (
                "Lactose (allolactose) inactivates the repressor, so it leaves the operator.",
                2,
                [
                    "lactose/allolactose binds and inactivates the repressor",
                    "repressor releases the operator",
                ],
                [
                    "says lactose activates the repressor",
                    "says the repressor stays bound when lactose is present",
                ],
            ),
            (
                "Low glucose raises cAMP; cAMP-CAP binds and boosts transcription (positive control).",
                2,
                [
                    "low glucose raises cAMP",
                    "cAMP-CAP complex binds the promoter",
                    "increases/activates transcription",
                ],
                ["says high glucose increases cAMP", "says CAP represses the operon"],
            ),
        ],
        "With lactose present, allolactose inactivates the lac repressor, freeing the "
        "operator. With glucose low, cAMP is high and cAMP-CAP binds upstream to strongly "
        "promote RNA polymerase binding, so the operon is transcribed robustly.",
    ),
    frq(
        "bio-biochem-2-frq6",
        "Describe the sliding-filament model of skeletal muscle contraction: what slides "
        "relative to what, the role of Ca2+, and the immediate energy source for "
        "cross-bridge cycling.",
        "aamc::bio-biochem::musculoskeletal",
        [
            (
                "Actin (thin) filaments slide past myosin (thick) filaments; the sarcomere shortens.",
                2,
                [
                    "actin/thin filaments slide past myosin/thick filaments",
                    "sarcomere shortens",
                    "filament lengths unchanged",
                ],
                [
                    "says the filaments themselves shorten/contract",
                    "says myosin slides along the Z-line only",
                ],
            ),
            (
                "Ca2+ exposes binding sites (troponin/tropomyosin) and ATP powers cross-bridge cycling.",
                2,
                [
                    "Ca2+ binds troponin, moving tropomyosin to expose binding sites",
                    "ATP powers myosin cross-bridge cycling",
                ],
                [
                    "says Ca2+ directly breaks the cross-bridges as the energy source",
                    "says GTP powers contraction",
                ],
            ),
        ],
        "Thin (actin) filaments slide past thick (myosin) filaments, shortening the "
        "sarcomere without changing filament length. Ca2+ binds troponin, shifting "
        "tropomyosin to expose actin's myosin-binding sites, and ATP hydrolysis powers "
        "the myosin cross-bridge cycle.",
    ),
    frq(
        "bio-biochem-2-frq7",
        "Two genes are located close together on the same chromosome. Explain why they "
        "tend to be inherited together and what process can still separate them, and "
        "state how distance affects the chance of separation.",
        "aamc::bio-biochem::genetics",
        [
            (
                "Linked genes are inherited together because they are on the same chromosome.",
                2,
                [
                    "genes are linked / on the same chromosome",
                    "tend to be inherited together",
                    "violate independent assortment",
                ],
                [
                    "says linked genes assort independently",
                    "says they are on different chromosomes",
                ],
            ),
            (
                "Crossing over (recombination) can separate them; closer genes recombine less often.",
                2,
                [
                    "crossing over / recombination during meiosis",
                    "closer genes = lower recombination frequency",
                ],
                [
                    "says mitosis separates them",
                    "says closer genes recombine more often",
                ],
            ),
        ],
        "Genes close together on one chromosome are linked and tend to be inherited "
        "together, violating independent assortment. Crossing over during meiosis can "
        "recombine them; the closer they are, the less often a crossover falls between "
        "them, so the recombination frequency is lower.",
    ),
    frq(
        "bio-biochem-2-frq8",
        "Explain how a signal molecule that cannot cross the plasma membrane (e.g. a "
        "peptide hormone) still changes activity inside the cell. Name the general "
        "mechanism and one common second messenger.",
        "aamc::bio-biochem::signal-transduction",
        [
            (
                "Binds a cell-surface receptor that transduces the signal without the ligand entering.",
                2,
                [
                    "binds a membrane/cell-surface receptor",
                    "ligand does not enter the cell",
                    "receptor transduces the signal (e.g. GPCR)",
                ],
                [
                    "says the peptide hormone diffuses through the membrane",
                    "says it binds a cytoplasmic/nuclear receptor directly",
                ],
            ),
            (
                "Triggers a second messenger cascade (e.g. cAMP, IP3/Ca2+) that alters intracellular activity.",
                2,
                [
                    "second messenger such as cAMP or IP3/Ca2+",
                    "intracellular signaling cascade / kinase activation",
                ],
                [
                    "says the hormone directly edits DNA without a cascade",
                    "names ATP as the second messenger",
                ],
            ),
        ],
        "A peptide hormone binds a cell-surface receptor (e.g. a GPCR) and never enters "
        "the cell; the activated receptor triggers a second-messenger cascade (such as "
        "cAMP or IP3/Ca2+) that changes the activity of intracellular enzymes.",
    ),
    frq(
        "bio-biochem-2-frq9",
        "Phosphofructokinase-1 (PFK-1) is the main control point of glycolysis. State "
        "one activator and one inhibitor of PFK-1 and explain why each makes sense for "
        "the cell's energy state.",
        "aamc::bio-biochem::carbohydrates",
        [
            (
                "Gives a correct activator (e.g. AMP or F-2,6-BP) tied to low energy / need for glycolysis.",
                2,
                [
                    "AMP (or F-2,6-bisphosphate) activates PFK-1",
                    "signals low energy / high AMP:ATP",
                ],
                ["says ATP activates PFK-1", "says citrate activates PFK-1"],
            ),
            (
                "Gives a correct inhibitor (e.g. ATP or citrate) tied to high energy / abundant fuel.",
                2,
                [
                    "ATP (or citrate) inhibits PFK-1",
                    "signals high energy / abundant building blocks",
                ],
                ["says AMP inhibits PFK-1", "says low ATP inhibits PFK-1"],
            ),
        ],
        "PFK-1 is activated by AMP (and fructose-2,6-bisphosphate), signaling low energy "
        "so glycolysis should run, and inhibited by ATP and citrate, signaling that "
        "energy and biosynthetic precursors are already abundant.",
    ),
    frq(
        "bio-biochem-2-frq10",
        "Explain how membrane fluidity is affected by (a) increasing the proportion of "
        "unsaturated fatty acid tails and (b) cholesterol at body temperature.",
        "aamc::bio-biochem::lipids",
        [
            (
                "Unsaturated tails (kinks) increase fluidity by preventing tight packing.",
                2,
                [
                    "unsaturated tails have kinks/double bonds",
                    "prevent tight packing",
                    "increase fluidity",
                ],
                [
                    "says unsaturated tails decrease fluidity",
                    "says saturated tails increase fluidity",
                ],
            ),
            (
                "Cholesterol buffers fluidity — at body/high temperature it reduces fluidity.",
                2,
                [
                    "cholesterol buffers/moderates fluidity",
                    "at high/body temperature it decreases fluidity",
                ],
                [
                    "says cholesterol always increases fluidity",
                    "says cholesterol has no effect on the membrane",
                ],
            ),
        ],
        "Unsaturated fatty acid tails have kinks that stop phospholipids from packing "
        "tightly, raising fluidity. Cholesterol acts as a fluidity buffer: at body/high "
        "temperature it restrains movement and reduces fluidity (while preventing rigid "
        "packing at low temperature).",
    ),
    frq(
        "bio-biochem-2-frq11",
        "An amino acid has an acidic side chain. At physiological pH (7.4), well above "
        "its side-chain pKa, what is the charge on that side chain and why? Explain "
        "using the relationship between pH and pKa.",
        "aamc::bio-biochem::amino-acids",
        [
            (
                "At pH above the pKa the acidic group is deprotonated / negatively charged.",
                2,
                ["deprotonated at pH above pKa", "negatively charged side chain"],
                [
                    "says it is protonated/positive at pH above pKa",
                    "says charge is neutral regardless of pKa",
                ],
            ),
            (
                "Explains via Henderson-Hasselbalch: pH > pKa favors the conjugate base form.",
                2,
                [
                    "pH > pKa favors the deprotonated/conjugate-base form",
                    "Henderson-Hasselbalch reasoning",
                ],
                [
                    "says pH > pKa favors the protonated form",
                    "says pKa does not determine protonation state",
                ],
            ),
        ],
        "Because pH 7.4 is above the acidic side chain's pKa, the group is mostly "
        "deprotonated and therefore negatively charged. By Henderson-Hasselbalch, when "
        "pH exceeds pKa the conjugate-base (deprotonated) form predominates.",
    ),
    frq(
        "bio-biochem-2-frq12",
        "For the exothermic equilibrium N2 + 3H2 ⇌ 2NH3, predict and justify (using Le "
        "Chatelier's principle) the effect on NH3 yield of (a) increasing pressure and "
        "(b) increasing temperature.",
        "aamc::bio-biochem::gen-chem",
        [
            (
                "Higher pressure shifts toward fewer gas moles (the products), increasing NH3.",
                2,
                [
                    "increased pressure shifts toward fewer moles of gas",
                    "shifts toward products / more NH3",
                ],
                [
                    "says higher pressure shifts toward reactants",
                    "says pressure has no effect",
                ],
            ),
            (
                "Higher temperature shifts an exothermic reaction toward reactants, decreasing NH3.",
                2,
                [
                    "higher temperature favors reactants for an exothermic reaction",
                    "decreases NH3 yield",
                ],
                [
                    "says higher temperature increases NH3 yield",
                    "treats the reaction as endothermic",
                ],
            ),
        ],
        "By Le Chatelier, raising pressure shifts the equilibrium toward the side with "
        "fewer gas moles (2 mol NH3 vs 4 mol reactants), increasing NH3. Raising "
        "temperature adds heat, which shifts this exothermic reaction toward reactants, "
        "decreasing NH3 yield.",
    ),
    frq(
        "bio-biochem-2-frq13",
        "Compare an SN1 and an SN2 substitution with respect to (a) the rate-law "
        "dependence on nucleophile concentration and (b) the effect on stereochemistry "
        "at the reacting carbon.",
        "aamc::bio-biochem::orgo",
        [
            (
                "SN2 is bimolecular (rate depends on nucleophile) with backside attack / inversion.",
                2,
                [
                    "SN2 rate depends on nucleophile concentration (second order)",
                    "inversion of configuration / backside attack",
                ],
                [
                    "says SN2 rate is independent of nucleophile",
                    "says SN2 gives retention only",
                ],
            ),
            (
                "SN1 is unimolecular (rate independent of nucleophile) via a carbocation, giving racemization.",
                2,
                [
                    "SN1 rate independent of nucleophile (first order)",
                    "planar carbocation intermediate",
                    "racemization / mixture of configurations",
                ],
                [
                    "says SN1 depends on nucleophile concentration",
                    "says SN1 gives clean inversion",
                ],
            ),
        ],
        "SN2 is second order—its rate depends on nucleophile concentration—and proceeds "
        "by backside attack, inverting configuration. SN1 is first order (rate "
        "independent of nucleophile) via a planar carbocation, so the nucleophile can "
        "attack either face, giving racemization.",
    ),
]

# ---------------------------------------------------------------------------
# chem-phys-1  (gen-chem 4, physics 3, biochemistry 3, orgo 2, biology 1 = 13)
# ---------------------------------------------------------------------------
CHEM_PHYS_1 = [
    frq(
        "chem-phys-1-frq1",
        "Propane combusts: C3H8 + 5 O2 → 3 CO2 + 4 H2O. If 2.0 mol of propane reacts "
        "with 8.0 mol of O2, identify the limiting reagent and state how many moles of "
        "CO2 form. Show the reasoning.",
        "aamc::chem-phys::stoichiometry",
        [
            (
                "Identifies O2 as limiting (needs 10 mol O2 for 2 mol propane; only 8 available).",
                2,
                [
                    "O2 is limiting",
                    "2 mol propane needs 10 mol O2",
                    "only 8 mol O2 available",
                ],
                ["says propane is limiting", "ignores the 1:5 propane:O2 ratio"],
            ),
            (
                "Computes CO2 from the limiting O2: 8 mol O2 × (3 CO2 / 5 O2) = 4.8 mol CO2.",
                2,
                ["uses 3 CO2 per 5 O2", "4.8 mol CO2"],
                ["computes 6 mol CO2 from propane", "uses the wrong mole ratio"],
            ),
        ],
        "2.0 mol propane would need 10 mol O2, but only 8.0 mol is present, so O2 is "
        "limiting. Using the 5 O2 : 3 CO2 ratio, 8.0 mol O2 yields 8.0 × 3/5 = 4.8 mol CO2.",
    ),
    frq(
        "chem-phys-1-frq2",
        "A weak acid HA has pKa = 4.8. In a solution buffered at pH 4.8, what is the "
        "approximate ratio of [A⁻] to [HA], and why? Use the Henderson-Hasselbalch "
        "relationship.",
        "aamc::chem-phys::acid-base",
        [
            (
                "States the ratio [A⁻]/[HA] ≈ 1 when pH = pKa.",
                2,
                ["ratio is 1:1 / equal", "[A-] approximately equals [HA]"],
                ["says the ratio is 10:1", "says all acid is dissociated"],
            ),
            (
                "Justifies with Henderson-Hasselbalch (pH = pKa + log([A⁻]/[HA]); log term = 0).",
                2,
                ["pH = pKa + log([A-]/[HA])", "log ratio = 0 when pH = pKa"],
                ["ignores the pKa relationship", "says pH equals concentration"],
            ),
        ],
        "When pH equals pKa, Henderson-Hasselbalch (pH = pKa + log[A⁻]/[HA]) requires the "
        "log term to be 0, so [A⁻]/[HA] = 1 — the acid is half dissociated.",
    ),
    frq(
        "chem-phys-1-frq3",
        "A reaction has ΔH < 0 and ΔS < 0. State how the spontaneity (sign of ΔG) "
        "depends on temperature, using ΔG = ΔH − TΔS, and say at which temperatures it "
        "is spontaneous.",
        "aamc::chem-phys::thermodynamics",
        [
            (
                "Uses ΔG = ΔH − TΔS with ΔH<0 and ΔS<0 (so −TΔS is positive and grows with T).",
                2,
                [
                    "ΔG = ΔH − TΔS",
                    "−TΔS is positive because ΔS<0",
                    "the TΔS term grows with temperature",
                ],
                ["says ΔG is independent of temperature", "treats −TΔS as negative"],
            ),
            (
                "Concludes spontaneous (ΔG<0) only at low temperature.",
                2,
                [
                    "spontaneous at low temperature",
                    "nonspontaneous at high temperature",
                ],
                [
                    "says spontaneous at all temperatures",
                    "says spontaneous at high temperature",
                ],
            ),
        ],
        "With ΔH<0 and ΔS<0, ΔG = ΔH − TΔS has a negative ΔH but a positive −TΔS term that "
        "grows with T. So ΔG is negative (spontaneous) only at low temperature and "
        "becomes positive at high temperature.",
    ),
    frq(
        "chem-phys-1-frq4",
        "An ideal gas is held at constant temperature and its volume is halved. State "
        "what happens to its pressure and justify using the ideal gas law.",
        "aamc::chem-phys::ideal-gas",
        [
            (
                "States pressure doubles.",
                2,
                ["pressure doubles", "pressure increases twofold"],
                ["says pressure halves", "says pressure is unchanged"],
            ),
            (
                "Justifies with PV = nRT at constant T, n (Boyle's law: P ∝ 1/V).",
                2,
                [
                    "PV = nRT with T and n constant",
                    "P inversely proportional to V (Boyle's law)",
                ],
                ["says P proportional to V", "invokes a temperature change"],
            ),
        ],
        "At constant T and n, PV = nRT means PV is constant, so P ∝ 1/V (Boyle's law). "
        "Halving V doubles P.",
    ),
    frq(
        "chem-phys-1-frq5",
        "A ball is thrown horizontally off a cliff. Ignoring air resistance, compare its "
        "horizontal and vertical motions and explain what determines the time it takes "
        "to hit the ground.",
        "aamc::chem-phys::kinematics",
        [
            (
                "Horizontal velocity is constant; vertical motion accelerates at g (independent axes).",
                2,
                [
                    "horizontal velocity constant (no horizontal acceleration)",
                    "vertical accelerates at g",
                    "the two axes are independent",
                ],
                [
                    "says horizontal velocity decreases due to gravity",
                    "says gravity acts horizontally",
                ],
            ),
            (
                "Time to land depends only on the vertical drop (height) and g, not horizontal speed.",
                2,
                [
                    "time depends on the fall height and g",
                    "independent of horizontal launch speed",
                ],
                [
                    "says a faster horizontal throw lands later",
                    "says horizontal speed sets the fall time",
                ],
            ),
        ],
        "Gravity acts only vertically, so horizontal velocity stays constant while the "
        "vertical velocity grows at g; the axes are independent. The fall time is set "
        "solely by the drop height and g (t = √(2h/g)), regardless of the horizontal "
        "launch speed.",
    ),
    frq(
        "chem-phys-1-frq6",
        "A 2 kg cart moving at 3 m/s coasts to a stop on a level track due to friction. "
        "Using the work-energy theorem, state how much work friction did and explain the "
        "energy transformation.",
        "aamc::chem-phys::work-energy",
        [
            (
                "Computes work by friction = −ΔKE = −(½mv²) = −9 J.",
                2,
                [
                    "work-energy theorem: W = ΔKE",
                    "initial KE = ½·2·3² = 9 J",
                    "friction did −9 J",
                ],
                [
                    "computes +9 J for friction",
                    "uses momentum instead of kinetic energy",
                ],
            ),
            (
                "Explains the KE is dissipated as heat (nonconservative work).",
                2,
                [
                    "kinetic energy converted to heat/thermal energy",
                    "friction is nonconservative",
                ],
                [
                    "says energy is stored as potential energy",
                    "says energy is destroyed",
                ],
            ),
        ],
        "The cart's initial KE is ½·2·3² = 9 J and its final KE is 0, so by the "
        "work-energy theorem friction did W = ΔKE = −9 J. That kinetic energy is "
        "dissipated as heat, since friction is a nonconservative force.",
    ),
    frq(
        "chem-phys-1-frq7",
        "An ideal fluid flows through a horizontal pipe that narrows. Using the "
        "continuity equation and Bernoulli's principle, state what happens to the fluid's "
        "speed and pressure in the narrow section.",
        "aamc::chem-phys::fluids",
        [
            (
                "Continuity: speed increases where the pipe narrows (A·v constant).",
                2,
                [
                    "continuity equation A·v = constant",
                    "speed increases in the narrow section",
                ],
                ["says speed decreases where it narrows", "says flow rate changes"],
            ),
            (
                "Bernoulli: higher speed means lower pressure in the narrow section.",
                2,
                [
                    "Bernoulli: faster flow = lower pressure",
                    "pressure decreases in the narrow section",
                ],
                [
                    "says pressure increases where speed increases",
                    "ignores the speed-pressure tradeoff",
                ],
            ),
        ],
        "By continuity (A·v constant), the fluid speeds up in the narrow section. By "
        "Bernoulli's principle, that higher speed corresponds to lower pressure there.",
    ),
    frq(
        "chem-phys-1-frq8",
        "Glycine has an amino group (pKa ≈ 9.6) and a carboxyl group (pKa ≈ 2.3). "
        "Describe its predominant charge form (zwitterion) at physiological pH 7.4 and "
        "explain why.",
        "aamc::chem-phys::amino-acids",
        [
            (
                "Carboxyl is deprotonated (−) because pH ≫ its pKa (2.3).",
                2,
                ["carboxyl deprotonated / negative", "pH is well above pKa 2.3"],
                ["says carboxyl is protonated at pH 7.4", "ignores the carboxyl pKa"],
            ),
            (
                "Amino group is protonated (+) because pH < its pKa (9.6); net neutral zwitterion.",
                2,
                [
                    "amino group protonated / positive",
                    "pH below pKa 9.6",
                    "net zwitterion / net neutral",
                ],
                [
                    "says amino group is deprotonated at pH 7.4",
                    "says the molecule is net charged",
                ],
            ),
        ],
        "At pH 7.4 the carboxyl (pKa 2.3) is deprotonated and negative, while the amino "
        "group (pKa 9.6) is still protonated and positive. Glycine is therefore a "
        "zwitterion with no net charge.",
    ),
    frq(
        "chem-phys-1-frq9",
        "For a Michaelis-Menten enzyme, define Km in words and explain what a low Km "
        "indicates about the enzyme's affinity for its substrate.",
        "aamc::chem-phys::enzyme-kinetics",
        [
            (
                "Km is the substrate concentration at half of Vmax.",
                2,
                ["Km = substrate concentration at half Vmax", "[S] giving ½ Vmax"],
                ["says Km is the maximum rate", "says Km is the enzyme concentration"],
            ),
            (
                "A low Km means high affinity (half-max reached at low substrate).",
                2,
                [
                    "low Km = high affinity",
                    "reaches half-max at low substrate concentration",
                ],
                ["says low Km means low affinity", "says Km is unrelated to affinity"],
            ),
        ],
        "Km is the substrate concentration at which the reaction runs at half its maximal "
        "velocity. A low Km means the enzyme reaches half-max at low substrate — i.e. it "
        "has high affinity for the substrate.",
    ),
    frq(
        "chem-phys-1-frq10",
        "Cells couple the energetically unfavorable synthesis of a molecule to ATP "
        "hydrolysis. Explain how coupling makes the overall process favorable in terms "
        "of ΔG.",
        "aamc::chem-phys::bioenergetics",
        [
            (
                "ATP hydrolysis is exergonic (large negative ΔG).",
                2,
                [
                    "ATP hydrolysis has negative ΔG / is exergonic",
                    "releases free energy",
                ],
                [
                    "says ATP hydrolysis is endergonic",
                    "says ATP hydrolysis has positive ΔG",
                ],
            ),
            (
                "Summed ΔG of coupled reactions is negative, so the overall process is spontaneous.",
                2,
                ["ΔG values add", "coupled total ΔG is negative / spontaneous"],
                [
                    "says the unfavorable reaction proceeds without a negative total ΔG",
                    "says coupling changes each reaction's ΔG sign individually",
                ],
            ),
        ],
        "ATP hydrolysis is strongly exergonic (large negative ΔG). When an unfavorable "
        "(positive-ΔG) reaction is coupled to it, the ΔG values add; as long as the sum "
        "is negative, the overall coupled process is spontaneous.",
    ),
    frq(
        "chem-phys-1-frq11",
        "Distinguish constitutional (structural) isomers from stereoisomers, and give a "
        "one-line example of each for molecules sharing the formula C4H10 or C4H8.",
        "aamc::chem-phys::isomerism",
        [
            (
                "Constitutional isomers: same formula, different connectivity/bonding.",
                2,
                [
                    "same molecular formula",
                    "different connectivity / atom-to-atom bonding",
                    "e.g. butane vs isobutane",
                ],
                [
                    "says constitutional isomers differ only in 3D arrangement",
                    "says they have different formulas",
                ],
            ),
            (
                "Stereoisomers: same connectivity, different spatial arrangement (e.g. cis/trans-2-butene).",
                2,
                [
                    "same connectivity",
                    "differ in spatial/3D arrangement",
                    "e.g. cis vs trans-2-butene",
                ],
                [
                    "says stereoisomers differ in connectivity",
                    "conflates them with constitutional isomers",
                ],
            ),
        ],
        "Constitutional (structural) isomers share a molecular formula but differ in "
        "connectivity (e.g. butane vs isobutane, both C4H10). Stereoisomers share "
        "connectivity but differ in spatial arrangement (e.g. cis- vs trans-2-butene, "
        "both C4H8).",
    ),
    frq(
        "chem-phys-1-frq12",
        "Rank a carboxylic acid, an alcohol, and an alkane by boiling point and justify "
        "the order using intermolecular forces.",
        "aamc::chem-phys::functional-groups",
        [
            (
                "Orders carboxylic acid > alcohol > alkane.",
                2,
                ["carboxylic acid highest", "alcohol middle", "alkane lowest"],
                [
                    "puts the alkane highest",
                    "puts the alcohol above the carboxylic acid",
                ],
            ),
            (
                "Justifies by hydrogen bonding vs only London dispersion (alkane).",
                2,
                [
                    "carboxylic acid/alcohol hydrogen bond",
                    "carboxylic acids H-bond most strongly (dimers)",
                    "alkane has only London dispersion",
                ],
                [
                    "says alkanes hydrogen bond",
                    "attributes the order to molecular weight alone",
                ],
            ),
        ],
        "Boiling point: carboxylic acid > alcohol > alkane. Carboxylic acids hydrogen "
        "bond most strongly (they can form dimers), alcohols hydrogen bond but less, and "
        "alkanes have only weak London dispersion forces, so they boil lowest.",
    ),
    frq(
        "chem-phys-1-frq13",
        "Explain how the countercurrent arrangement of blood flow and water flow in fish "
        "gills maximizes oxygen extraction compared with concurrent (same-direction) flow.",
        "aamc::chem-phys::physiology",
        [
            (
                "Countercurrent maintains a favorable O2 gradient along the entire exchange surface.",
                2,
                [
                    "countercurrent keeps a diffusion gradient along the whole length",
                    "blood always meets water with higher O2",
                ],
                [
                    "says the gradient disappears partway (that is concurrent)",
                    "says flow direction does not matter",
                ],
            ),
            (
                "Concurrent flow equilibrates partway, so less O2 is extracted.",
                2,
                [
                    "concurrent flow equilibrates / gradient vanishes at equilibrium",
                    "extracts less O2",
                ],
                [
                    "says concurrent flow extracts more O2",
                    "says both arrangements extract the same",
                ],
            ),
        ],
        "In countercurrent exchange, blood and water flow in opposite directions, so "
        "blood always encounters water with a slightly higher O2 concentration and a "
        "diffusion gradient is maintained along the whole gill. Concurrent flow would "
        "equilibrate partway, capping extraction, so countercurrent removes far more O2.",
    ),
]

# ---------------------------------------------------------------------------
# chem-phys-2  (gen-chem 4, physics 3, biochemistry 3, orgo 2, biology 1 = 13)
# ---------------------------------------------------------------------------
CHEM_PHYS_2 = [
    frq(
        "chem-phys-2-frq1",
        "For a saturated solution of a sparingly soluble salt in equilibrium with its "
        "solid, explain what Ksp represents and predict (with justification) how adding "
        "a common ion shifts the dissolved-ion concentration.",
        "aamc::chem-phys::equilibrium",
        [
            (
                "Ksp is the equilibrium product of dissolved ion concentrations for the saturated solution.",
                2,
                [
                    "Ksp = product of dissolved ion concentrations at saturation",
                    "solubility-product equilibrium constant",
                ],
                [
                    "says Ksp changes when you add common ion",
                    "says Ksp is the amount of solid",
                ],
            ),
            (
                "Common-ion effect shifts equilibrium toward solid, lowering solubility.",
                2,
                [
                    "common ion shifts equilibrium toward the solid (Le Chatelier)",
                    "solubility decreases",
                ],
                [
                    "says added common ion increases solubility",
                    "says Ksp increases with common ion",
                ],
            ),
        ],
        "Ksp is the product of the dissolved ion concentrations for a saturated solution "
        "(a constant at a given temperature). Adding a common ion raises one ion's "
        "concentration, so by Le Chatelier the equilibrium shifts toward solid and the "
        "salt's solubility decreases (Ksp itself is unchanged).",
    ),
    frq(
        "chem-phys-2-frq2",
        "In a galvanic (voltaic) cell, identify where oxidation and reduction occur "
        "(anode vs cathode) and state the sign of the cell potential for a spontaneous "
        "cell.",
        "aamc::chem-phys::electrochemistry",
        [
            (
                "Oxidation at the anode, reduction at the cathode.",
                2,
                ["oxidation at the anode", "reduction at the cathode"],
                ["swaps anode and cathode", "says both occur at one electrode"],
            ),
            (
                "Spontaneous galvanic cell has positive cell potential (Ecell > 0, ΔG < 0).",
                2,
                ["Ecell positive for a spontaneous cell", "corresponds to negative ΔG"],
                [
                    "says a spontaneous cell has negative Ecell",
                    "says Ecell = 0 at spontaneity",
                ],
            ),
        ],
        "In a galvanic cell, oxidation occurs at the anode and reduction at the cathode "
        "(mnemonic: 'an ox, red cat'). A spontaneous cell has a positive cell potential "
        "(Ecell > 0), corresponding to a negative ΔG.",
    ),
    frq(
        "chem-phys-2-frq3",
        "Explain the general periodic trend in atomic radius across a period (left to "
        "right) and give the underlying reason.",
        "aamc::chem-phys::periodic-trends",
        [
            (
                "Atomic radius decreases left to right across a period.",
                2,
                ["atomic radius decreases across a period", "smaller toward the right"],
                [
                    "says radius increases across a period",
                    "says radius is constant across a period",
                ],
            ),
            (
                "Attributes it to increasing effective nuclear charge pulling electrons in.",
                2,
                [
                    "increasing nuclear charge / effective nuclear charge",
                    "same shell / no new energy level",
                    "stronger pull on electrons",
                ],
                [
                    "attributes the decrease to adding new shells",
                    "says shielding increases across a period",
                ],
            ),
        ],
        "Atomic radius decreases across a period because protons are added to the nucleus "
        "while electrons fill the same shell; the rising effective nuclear charge pulls "
        "the electron cloud in more tightly.",
    ),
    frq(
        "chem-phys-2-frq4",
        "Adding a nonvolatile solute to a solvent lowers the freezing point. Name this "
        "type of property and explain what it depends on (and does not depend on).",
        "aamc::chem-phys::solutions",
        [
            (
                "Identifies it as a colligative property.",
                2,
                ["colligative property", "freezing-point depression"],
                [
                    "calls it a chemical/reactive property",
                    "says it depends on the reaction",
                ],
            ),
            (
                "Depends on the number/concentration of dissolved particles, not their identity.",
                2,
                [
                    "depends on the number/concentration of particles",
                    "not on the identity of the solute",
                ],
                [
                    "says it depends on the chemical identity of the solute",
                    "says one mole of any solute gives different depression regardless of dissociation",
                ],
            ),
        ],
        "Freezing-point depression is a colligative property: it depends only on the "
        "number (concentration) of dissolved solute particles, not on their chemical "
        "identity (so a salt that dissociates into more particles depresses it more).",
    ),
    frq(
        "chem-phys-2-frq5",
        "Two resistors are connected in series across a battery. State how the current "
        "through each compares and how the total resistance relates to the individual "
        "resistances, with justification.",
        "aamc::chem-phys::circuits",
        [
            (
                "Same current flows through both (single path).",
                2,
                [
                    "same current through each resistor in series",
                    "single path / current is conserved",
                ],
                ["says current divides between them", "treats them as parallel"],
            ),
            (
                "Total resistance is the sum (R_total = R1 + R2).",
                2,
                ["resistances add in series", "R_total = R1 + R2"],
                [
                    "says resistances add reciprocally in series",
                    "says total resistance is less than either",
                ],
            ),
        ],
        "In series there is a single current path, so the same current flows through "
        "both resistors. The resistances add: R_total = R1 + R2 (greater than either "
        "alone).",
    ),
    frq(
        "chem-phys-2-frq6",
        "An object is placed beyond the focal length of a converging (convex) lens. "
        "Describe the image formed (real/virtual, orientation) and justify briefly.",
        "aamc::chem-phys::optics",
        [
            (
                "Image is real and inverted.",
                2,
                ["real image", "inverted"],
                ["says virtual image", "says upright/erect image"],
            ),
            (
                "Justifies via converging rays / positive image distance for object beyond f.",
                2,
                [
                    "rays converge to form the image on the far side",
                    "object beyond focal length gives a real image (positive image distance)",
                ],
                [
                    "says the rays diverge",
                    "says a converging lens can only form virtual images",
                ],
            ),
        ],
        "For an object beyond the focal length, a converging lens forms a real, inverted "
        "image: the refracted rays actually converge on the opposite side of the lens "
        "(positive image distance).",
    ),
    frq(
        "chem-phys-2-frq7",
        "A source of sound moves toward a stationary observer. State how the observed "
        "frequency compares to the emitted frequency and name the effect, with a "
        "one-sentence reason.",
        "aamc::chem-phys::waves-sound",
        [
            (
                "Observed frequency is higher than emitted (Doppler effect).",
                2,
                ["observed frequency higher / pitch rises", "Doppler effect"],
                [
                    "says observed frequency is lower for an approaching source",
                    "says frequency is unchanged",
                ],
            ),
            (
                "Reasons that approaching source compresses wavefronts (shorter wavelength).",
                2,
                [
                    "wavefronts compressed / bunched",
                    "shorter wavelength as source approaches",
                ],
                [
                    "says the wavefronts spread out as it approaches",
                    "attributes it to louder volume",
                ],
            ),
        ],
        "An approaching source raises the observed frequency (Doppler effect): the "
        "source's motion compresses the wavefronts ahead of it, shortening the "
        "wavelength the observer receives.",
    ),
    frq(
        "chem-phys-2-frq8",
        "Explain the Bohr effect: how does a decrease in pH (e.g. in exercising tissue) "
        "affect hemoglobin's affinity for O2, and why is this useful?",
        "aamc::chem-phys::hemoglobin",
        [
            (
                "Lower pH decreases hemoglobin's O2 affinity (right shift of the curve).",
                2,
                [
                    "lower pH decreases O2 affinity",
                    "rightward shift of the O2 dissociation curve",
                ],
                [
                    "says low pH increases O2 affinity",
                    "says pH has no effect on hemoglobin",
                ],
            ),
            (
                "Explains it promotes O2 unloading where metabolically active tissue needs it.",
                2,
                [
                    "releases/unloads more O2 to active tissue",
                    "matches O2 delivery to demand",
                ],
                [
                    "says it makes hemoglobin hold O2 more tightly in tissue",
                    "says it impairs O2 delivery",
                ],
            ),
        ],
        "The Bohr effect: lower pH (more CO2/acid in active tissue) lowers hemoglobin's O2 "
        "affinity, shifting the dissociation curve right. This promotes O2 unloading "
        "exactly where metabolically active tissue needs it most.",
    ),
    frq(
        "chem-phys-2-frq9",
        "Compare saturated and unsaturated fatty acids in terms of molecular shape and "
        "the resulting melting point, and explain the connection.",
        "aamc::chem-phys::lipids",
        [
            (
                "Saturated = straight chains that pack tightly; unsaturated = kinked (cis double bonds).",
                2,
                [
                    "saturated chains are straight and pack tightly",
                    "unsaturated have kinks from cis double bonds",
                ],
                [
                    "says saturated fatty acids have kinks",
                    "says unsaturated chains pack more tightly",
                ],
            ),
            (
                "Tighter packing (saturated) → higher melting point; kinks (unsaturated) → lower.",
                2,
                [
                    "saturated have higher melting points",
                    "unsaturated have lower melting points",
                ],
                [
                    "says unsaturated fats have higher melting points",
                    "says packing does not affect melting point",
                ],
            ),
        ],
        "Saturated fatty acids are straight and pack tightly, giving strong intermolecular "
        "contact and higher melting points (solids at room temp). Cis double bonds kink "
        "unsaturated chains, preventing tight packing and lowering the melting point "
        "(oils).",
    ),
    frq(
        "chem-phys-2-frq10",
        "In the mitochondrial electron transport chain, explain the role of oxygen as "
        "the final electron acceptor and what happens to the chain if oxygen is absent.",
        "aamc::chem-phys::redox-metabolism",
        [
            (
                "O2 is the terminal electron acceptor, forming water.",
                2,
                [
                    "oxygen is the final/terminal electron acceptor",
                    "forms water",
                    "accepts electrons at complex IV",
                ],
                [
                    "says CO2 is the final electron acceptor",
                    "says O2 donates electrons to the chain",
                ],
            ),
            (
                "Without O2 the chain backs up (carriers stay reduced), halting ETC and its ATP.",
                2,
                [
                    "without O2 electrons cannot be passed on",
                    "carriers become fully reduced / chain backs up",
                    "oxidative phosphorylation stops",
                ],
                [
                    "says the chain runs normally without O2",
                    "says glycolysis stops immediately without O2",
                ],
            ),
        ],
        "Oxygen is the terminal electron acceptor at complex IV, combining with electrons "
        "and protons to form water and keeping electrons flowing. Without O2, the "
        "carriers stay reduced, the chain backs up, and oxidative phosphorylation (and "
        "its ATP output) stops.",
    ),
    frq(
        "chem-phys-2-frq11",
        "A tertiary alkyl halide reacts with a weak nucleophile in a polar protic "
        "solvent. Predict whether SN1 or SN2 dominates and justify with two reasons.",
        "aamc::chem-phys::orgo-reactions",
        [
            (
                "Predicts SN1.",
                2,
                ["SN1 dominates"],
                [
                    "says SN2 dominates for a tertiary substrate",
                    "predicts elimination only",
                ],
            ),
            (
                "Justifies: tertiary carbocation is stabilized AND polar protic solvent / weak nucleophile favor SN1.",
                2,
                [
                    "tertiary substrate gives a stable carbocation",
                    "polar protic solvent and weak nucleophile favor SN1",
                ],
                [
                    "says a weak nucleophile favors SN2",
                    "says tertiary substrates favor SN2 due to sterics",
                ],
            ),
        ],
        "SN1 dominates: a tertiary substrate forms a stabilized 3° carbocation, and a weak "
        "nucleophile in a polar protic solvent (which stabilizes the ions) both favor the "
        "stepwise SN1 pathway over SN2 (which is also blocked sterically at 3° carbon).",
    ),
    frq(
        "chem-phys-2-frq12",
        "In ¹H NMR, explain what the (a) number of signals and (b) integration of a peak "
        "tell you about a molecule.",
        "aamc::chem-phys::nmr",
        [
            (
                "Number of signals = number of chemically distinct (nonequivalent) hydrogen environments.",
                2,
                [
                    "number of signals = distinct/nonequivalent H environments",
                    "chemically inequivalent protons",
                ],
                [
                    "says number of signals = total number of hydrogens",
                    "says it gives the number of carbons",
                ],
            ),
            (
                "Integration (peak area) is proportional to the number of H in that environment.",
                2,
                [
                    "integration/area proportional to number of protons in that environment",
                    "gives relative H counts",
                ],
                [
                    "says integration gives the chemical shift",
                    "says integration gives coupling/splitting",
                ],
            ),
        ],
        "The number of ¹H NMR signals equals the number of chemically distinct hydrogen "
        "environments. The integration (area under a peak) is proportional to the number "
        "of hydrogens giving rise to that signal, so it reports relative H counts.",
    ),
    frq(
        "chem-phys-2-frq13",
        "A small nonpolar molecule crosses the lipid bilayer far faster than a similarly "
        "sized ion. Explain why, referring to the properties of the membrane interior.",
        "aamc::chem-phys::membrane-transport",
        [
            (
                "The bilayer interior is hydrophobic/nonpolar.",
                2,
                [
                    "membrane interior is hydrophobic/nonpolar",
                    "made of fatty acid tails",
                ],
                [
                    "says the interior is hydrophilic/polar",
                    "says the interior is charged",
                ],
            ),
            (
                "Nonpolar molecules dissolve through it; ions are repelled/require a huge energy cost (need channels).",
                2,
                [
                    "nonpolar molecules dissolve in and pass freely",
                    "ions face a large energy barrier / need channels or transporters",
                ],
                [
                    "says ions cross the bilayer freely by simple diffusion",
                    "says nonpolar molecules need protein channels",
                ],
            ),
        ],
        "The bilayer's interior is a hydrophobic, nonpolar region of fatty-acid tails. "
        "Small nonpolar molecules dissolve in and pass through freely, whereas a charged "
        "ion faces a large energetic barrier and can cross only via channels or "
        "transporters.",
    ),
]

# ---------------------------------------------------------------------------
# psych-soc-1  (psychology 8, sociology 4, biology 1 = 13)
# ---------------------------------------------------------------------------
PSYCH_SOC_1 = [
    frq(
        "psych-soc-1-frq1",
        "Distinguish classical conditioning from operant conditioning, naming the kind "
        "of behavior each governs and the key relationship the learner acquires.",
        "aamc::psych-soc::learning",
        [
            (
                "Classical: involuntary/reflexive response; associating two stimuli (CS with US).",
                2,
                [
                    "classical conditioning involves involuntary/reflexive responses",
                    "associates a neutral stimulus with an unconditioned stimulus",
                ],
                [
                    "says classical conditioning shapes voluntary behavior via consequences",
                    "conflates it with operant conditioning",
                ],
            ),
            (
                "Operant: voluntary behavior changed by its consequences (reinforcement/punishment).",
                2,
                [
                    "operant conditioning involves voluntary behavior",
                    "behavior changed by consequences (reinforcement/punishment)",
                ],
                [
                    "says operant conditioning pairs two stimuli",
                    "says operant conditioning acts on reflexes",
                ],
            ),
        ],
        "Classical conditioning shapes involuntary, reflexive responses by associating a "
        "neutral stimulus with an unconditioned stimulus. Operant conditioning changes "
        "voluntary behavior according to its consequences (reinforcement or punishment).",
    ),
    frq(
        "psych-soc-1-frq2",
        "Distinguish negative reinforcement from punishment, and state the effect each "
        "has on the frequency of the target behavior.",
        "aamc::psych-soc::learning",
        [
            (
                "Negative reinforcement removes an aversive stimulus and increases the behavior.",
                2,
                [
                    "negative reinforcement removes/avoids an aversive stimulus",
                    "increases the behavior",
                ],
                [
                    "says negative reinforcement decreases behavior",
                    "equates negative reinforcement with punishment",
                ],
            ),
            (
                "Punishment decreases the behavior.",
                2,
                ["punishment decreases/suppresses the behavior"],
                [
                    "says punishment increases behavior",
                    "says punishment and reinforcement have the same effect",
                ],
            ),
        ],
        "Negative reinforcement removes an aversive stimulus, which increases the target "
        "behavior; it is not punishment. Punishment (positive or negative) decreases the "
        "behavior.",
    ),
    frq(
        "psych-soc-1-frq3",
        "Describe the three-stage (Atkinson-Shiffrin) model of memory, naming the stages "
        "in order and one feature that distinguishes short-term from long-term memory.",
        "aamc::psych-soc::memory",
        [
            (
                "Names sensory memory → short-term (working) memory → long-term memory, in order.",
                2,
                [
                    "sensory memory",
                    "short-term/working memory",
                    "long-term memory",
                    "in that order",
                ],
                ["puts the stages out of order", "omits sensory memory entirely"],
            ),
            (
                "Contrasts limited/brief short-term with large/durable long-term (capacity or duration).",
                2,
                [
                    "short-term is limited capacity / brief duration",
                    "long-term is large capacity / durable",
                ],
                [
                    "says short-term memory is unlimited and permanent",
                    "says long-term memory holds only a few items for seconds",
                ],
            ),
        ],
        "Information flows sensory memory → short-term (working) memory → long-term memory. "
        "Short-term memory holds a limited amount (~7 items) briefly, whereas long-term "
        "memory has essentially unlimited capacity and long duration.",
    ),
    frq(
        "psych-soc-1-frq4",
        "Explain the difference between proactive and retroactive interference in "
        "forgetting, giving the direction of interference in each.",
        "aamc::psych-soc::memory",
        [
            (
                "Proactive: old learning interferes with new memories.",
                2,
                ["proactive interference: old/prior learning disrupts new learning"],
                [
                    "says proactive interference is new disrupting old",
                    "reverses the direction",
                ],
            ),
            (
                "Retroactive: new learning interferes with old memories.",
                2,
                [
                    "retroactive interference: new learning disrupts old/previous memories"
                ],
                [
                    "says retroactive interference is old disrupting new",
                    "conflates the two",
                ],
            ),
        ],
        "Proactive interference is when previously learned information disrupts recall of "
        "newly learned material; retroactive interference is when new learning disrupts "
        "recall of older material.",
    ),
    frq(
        "psych-soc-1-frq5",
        "Define the absolute threshold in sensation, and explain how signal detection "
        "theory adds to this idea by accounting for factors beyond stimulus intensity.",
        "aamc::psych-soc::sensation-perception",
        [
            (
                "Absolute threshold = minimum stimulus intensity detectable a set fraction (≈50%) of the time.",
                2,
                [
                    "minimum intensity detectable ~50% of the time",
                    "smallest detectable stimulus",
                ],
                [
                    "says absolute threshold is the smallest detectable difference between stimuli (that is difference threshold)"
                ],
            ),
            (
                "Signal detection theory adds non-sensory factors (expectation/motivation, response bias, noise).",
                2,
                [
                    "signal detection accounts for decision/response bias, expectations, or noise",
                    "detection is not purely about intensity",
                ],
                [
                    "says detection depends only on stimulus intensity",
                    "ignores observer/decision factors",
                ],
            ),
        ],
        "The absolute threshold is the minimum stimulus intensity a person can detect "
        "about 50% of the time. Signal detection theory adds that detection also depends "
        "on non-sensory factors—expectations, motivation, response bias, and background "
        "noise—not intensity alone.",
    ),
    frq(
        "psych-soc-1-frq6",
        "Contrast the availability heuristic with the representativeness heuristic, "
        "giving what each judgment is based on.",
        "aamc::psych-soc::cognition",
        [
            (
                "Availability: judging likelihood by how easily examples come to mind.",
                2,
                [
                    "availability heuristic: ease of recalling examples",
                    "how readily instances come to mind",
                ],
                [
                    "defines availability as matching a prototype",
                    "swaps the two heuristics",
                ],
            ),
            (
                "Representativeness: judging by similarity to a prototype/stereotype.",
                2,
                [
                    "representativeness heuristic: similarity to a prototype/stereotype/category"
                ],
                [
                    "defines representativeness as ease of recall",
                    "ignores prototype matching",
                ],
            ),
        ],
        "The availability heuristic judges probability by how easily instances come to "
        "mind, while the representativeness heuristic judges by how closely something "
        "matches a prototype or stereotype of a category.",
    ),
    frq(
        "psych-soc-1-frq7",
        "In Piaget's theory, distinguish assimilation from accommodation, and give the "
        "direction of change to the child's schema in each.",
        "aamc::psych-soc::cognition",
        [
            (
                "Assimilation: fitting new information into an existing schema (schema unchanged).",
                2,
                [
                    "assimilation fits new info into an existing schema",
                    "schema is not changed",
                ],
                ["says assimilation changes the schema", "swaps the two terms"],
            ),
            (
                "Accommodation: changing/creating a schema to fit new information.",
                2,
                [
                    "accommodation modifies or creates a schema",
                    "schema changes to fit new information",
                ],
                [
                    "says accommodation leaves the schema unchanged",
                    "conflates it with assimilation",
                ],
            ),
        ],
        "Assimilation incorporates new information into an existing schema without "
        "changing it; accommodation modifies or creates a schema to fit information that "
        "doesn't fit the old one.",
    ),
    frq(
        "psych-soc-1-frq8",
        "Contrast the James-Lange and Cannon-Bard theories of emotion with respect to "
        "the order/timing of physiological arousal and the conscious feeling of emotion.",
        "aamc::psych-soc::motivation-emotion",
        [
            (
                "James-Lange: physiological arousal comes first and the emotion is the interpretation of it.",
                2,
                [
                    "James-Lange: bodily arousal precedes/causes the emotion",
                    "emotion is the perception of the physiological response",
                ],
                ["says James-Lange has emotion causing arousal", "swaps the theories"],
            ),
            (
                "Cannon-Bard: arousal and the emotional experience occur simultaneously/independently.",
                2,
                [
                    "Cannon-Bard: arousal and emotion occur at the same time",
                    "simultaneous and independent",
                ],
                [
                    "says Cannon-Bard has arousal strictly before emotion",
                    "says Cannon-Bard requires cognitive labeling first",
                ],
            ),
        ],
        "James-Lange says physiological arousal occurs first and the felt emotion is our "
        "interpretation of that bodily state. Cannon-Bard says the arousal and the "
        "conscious emotion happen simultaneously and independently.",
    ),
    frq(
        "psych-soc-1-frq9",
        "Distinguish material culture from nonmaterial culture in sociology, giving an "
        "example of each.",
        "aamc::psych-soc::culture",
        [
            (
                "Material culture = physical objects/artifacts of a group (with an example).",
                2,
                [
                    "material culture is physical objects/artifacts",
                    "example such as tools, buildings, clothing",
                ],
                [
                    "says material culture is beliefs/values",
                    "gives a nonmaterial example for material culture",
                ],
            ),
            (
                "Nonmaterial culture = ideas/beliefs/values/norms (with an example).",
                2,
                [
                    "nonmaterial culture is ideas, beliefs, values, or norms",
                    "example such as language, customs, laws",
                ],
                [
                    "says nonmaterial culture is physical objects",
                    "gives a physical example for nonmaterial culture",
                ],
            ),
        ],
        "Material culture is the physical objects a group creates and uses (tools, "
        "buildings, clothing). Nonmaterial culture is its intangible ideas—beliefs, "
        "values, norms, and language.",
    ),
    frq(
        "psych-soc-1-frq10",
        "Distinguish a primary group from a secondary group in sociology, giving the "
        "nature of the relationships in each.",
        "aamc::psych-soc::social-groups",
        [
            (
                "Primary group: small, close, enduring, personal relationships (e.g. family).",
                2,
                [
                    "primary group has close/intimate, enduring, personal ties",
                    "example such as family or close friends",
                ],
                [
                    "says primary groups are large and impersonal",
                    "swaps the definitions",
                ],
            ),
            (
                "Secondary group: larger, impersonal, goal-/task-oriented relationships.",
                2,
                [
                    "secondary group is impersonal / task- or goal-oriented",
                    "example such as coworkers or a class",
                ],
                [
                    "says secondary groups are intimate and lifelong",
                    "conflates it with a primary group",
                ],
            ),
        ],
        "Primary groups are small and marked by close, enduring, personal relationships "
        "(e.g. family). Secondary groups are larger and impersonal, organized around a "
        "shared task or goal (e.g. coworkers).",
    ),
    frq(
        "psych-soc-1-frq11",
        "Define socialization and name two agents of socialization, explaining what each "
        "contributes.",
        "aamc::psych-soc::socialization",
        [
            (
                "Defines socialization as learning a society's norms, values, and behaviors.",
                2,
                [
                    "socialization = learning the norms/values/roles of society",
                    "process of internalizing culture",
                ],
                [
                    "defines socialization as being social/extroverted",
                    "says it is genetic transmission of behavior",
                ],
            ),
            (
                "Names two valid agents (e.g. family, school, peers, media) with a role for each.",
                2,
                [
                    "names two agents such as family, school, peers, or media",
                    "gives what each contributes",
                ],
                [
                    "names only one agent",
                    "names non-agents (e.g. weather) as agents of socialization",
                ],
            ),
        ],
        "Socialization is the lifelong process of learning and internalizing a society's "
        "norms, values, and roles. Agents include the family (earliest values and "
        "language), school (rules and knowledge), peers, and media—each transmitting "
        "cultural expectations.",
    ),
    frq(
        "psych-soc-1-frq12",
        "Using the functionalist distinction, give one manifest function and one latent "
        "function of a social institution such as schooling, and explain the difference.",
        "aamc::psych-soc::social-institutions",
        [
            (
                "Manifest function = intended, recognized consequence (e.g. schooling teaches skills).",
                2,
                [
                    "manifest function is intended/recognized",
                    "example such as education transmitting knowledge/skills",
                ],
                [
                    "defines manifest function as unintended",
                    "swaps manifest and latent",
                ],
            ),
            (
                "Latent function = unintended/hidden consequence (e.g. schooling as childcare or social networking).",
                2,
                [
                    "latent function is unintended/unrecognized",
                    "example such as childcare, friendship networks, dating",
                ],
                [
                    "defines latent function as the intended goal",
                    "conflates it with a dysfunction only",
                ],
            ),
        ],
        "A manifest function is an institution's intended, recognized consequence—e.g. "
        "schools teach academic skills. A latent function is an unintended, hidden "
        "consequence—e.g. schools also provide childcare and social networks.",
    ),
    frq(
        "psych-soc-1-frq13",
        "During a frightening event the body mobilizes for 'fight or flight.' Name the "
        "branch of the autonomic nervous system responsible and describe two of its "
        "physiological effects.",
        "aamc::psych-soc::biological-behavior",
        [
            (
                "Identifies the sympathetic nervous system.",
                2,
                [
                    "sympathetic nervous system",
                    "sympathetic branch of the autonomic nervous system",
                ],
                [
                    "says the parasympathetic system drives fight-or-flight",
                    "names the somatic nervous system",
                ],
            ),
            (
                "Gives two correct sympathetic effects (e.g. ↑ heart rate, pupil dilation, ↓ digestion).",
                2,
                [
                    "two effects such as increased heart rate, pupil dilation, bronchodilation, decreased digestion"
                ],
                [
                    "lists parasympathetic 'rest and digest' effects",
                    "gives only one effect",
                ],
            ),
        ],
        "The sympathetic nervous system drives fight-or-flight. Its effects include "
        "increased heart rate and blood pressure, pupil dilation, bronchodilation, and "
        "decreased digestive activity—preparing the body for action.",
    ),
]

# ---------------------------------------------------------------------------
# psych-soc-2  (psychology 8, sociology 4, biology 1 = 13)
# ---------------------------------------------------------------------------
PSYCH_SOC_2 = [
    frq(
        "psych-soc-2-frq1",
        "Distinguish the positive symptoms of schizophrenia from the negative symptoms, "
        "giving one example of each.",
        "aamc::psych-soc::psychological-disorders",
        [
            (
                "Positive symptoms = added/excess experiences (e.g. hallucinations, delusions).",
                2,
                [
                    "positive symptoms are added/abnormal experiences",
                    "example such as hallucinations or delusions",
                ],
                [
                    "says positive symptoms are 'good' symptoms",
                    "defines positive symptoms as losses/deficits",
                ],
            ),
            (
                "Negative symptoms = reductions/deficits in normal function (e.g. flat affect, avolition).",
                2,
                [
                    "negative symptoms are deficits/reductions in normal functioning",
                    "example such as flat affect, alogia, or avolition",
                ],
                [
                    "says negative symptoms are 'bad' symptoms",
                    "defines negative symptoms as added experiences",
                ],
            ),
        ],
        "Positive symptoms are additions to normal experience—hallucinations, delusions, "
        "disorganized speech. Negative symptoms are losses of normal function—flat "
        "affect, avolition, social withdrawal.",
    ),
    frq(
        "psych-soc-2-frq2",
        "Name the three levels of Kohlberg's theory of moral development in order, and "
        "state what guides moral reasoning at the first and last levels.",
        "aamc::psych-soc::development",
        [
            (
                "Names preconventional → conventional → postconventional, in order.",
                2,
                ["preconventional, conventional, postconventional", "in that order"],
                ["puts the levels out of order", "omits a level"],
            ),
            (
                "Preconventional = consequences to self (reward/punishment); postconventional = abstract principles.",
                2,
                [
                    "preconventional focuses on rewards/punishments/self-interest",
                    "postconventional focuses on abstract ethical principles/justice",
                ],
                [
                    "swaps preconventional and postconventional reasoning",
                    "says preconventional is based on universal principles",
                ],
            ),
        ],
        "Kohlberg's levels are preconventional, conventional, then postconventional. "
        "Preconventional reasoning is driven by rewards and punishments to the self; "
        "postconventional reasoning is guided by abstract ethical principles and justice.",
    ),
    frq(
        "psych-soc-2-frq3",
        "In Freud's structural model of personality, describe the roles of the id, ego, "
        "and superego and the principle each follows.",
        "aamc::psych-soc::personality",
        [
            (
                "Id = instinctual drives, pleasure principle; superego = morals/ideals.",
                2,
                [
                    "id is instinctual drives following the pleasure principle",
                    "superego represents morality/conscience/ideals",
                ],
                [
                    "says the id is the moral component",
                    "says the superego seeks immediate gratification",
                ],
            ),
            (
                "Ego = mediates id and superego via the reality principle.",
                2,
                [
                    "ego mediates between id and superego",
                    "ego follows the reality principle",
                ],
                [
                    "says the ego is purely instinctual",
                    "omits the ego's mediating/reality role",
                ],
            ),
        ],
        "The id houses instinctual drives and follows the pleasure principle; the "
        "superego embodies morals and ideals; the ego mediates between them and reality, "
        "operating on the reality principle.",
    ),
    frq(
        "psych-soc-2-frq4",
        "Explain cognitive dissonance theory: what produces the discomfort, and describe "
        "one way people typically reduce it.",
        "aamc::psych-soc::attitudes",
        [
            (
                "Dissonance arises from a conflict between attitudes/beliefs and behavior (or two cognitions).",
                2,
                [
                    "dissonance is discomfort from conflicting cognitions",
                    "mismatch between attitude/belief and behavior",
                ],
                ["says dissonance comes from agreement between beliefs and behavior"],
            ),
            (
                "People reduce it by changing an attitude, changing behavior, or adding justifying cognitions.",
                2,
                [
                    "reduce dissonance by changing the attitude, the behavior, or rationalizing/adding a cognition"
                ],
                [
                    "says people increase the conflict to feel better",
                    "gives no valid reduction strategy",
                ],
            ),
        ],
        "Cognitive dissonance is the discomfort felt when attitudes and behavior (or two "
        "beliefs) conflict. People relieve it by changing their attitude, changing their "
        "behavior, or adding a new cognition that justifies the inconsistency.",
    ),
    frq(
        "psych-soc-2-frq5",
        "Contrast REM sleep with non-REM (slow-wave) sleep, naming one physiological or "
        "experiential feature that distinguishes them.",
        "aamc::psych-soc::consciousness",
        [
            (
                "REM: rapid eye movement, vivid dreaming, high/awake-like brain activity, muscle atonia.",
                2,
                [
                    "REM has rapid eye movements and vivid dreaming",
                    "brain activity resembles wakefulness / paralysis of skeletal muscle",
                ],
                ["says REM is dreamless deep sleep", "swaps REM and NREM features"],
            ),
            (
                "NREM (esp. slow-wave): slow delta waves, deep restorative sleep, little/no vivid dreaming.",
                2,
                [
                    "NREM/slow-wave sleep has slow delta waves and is deep/restorative",
                    "little or no vivid dreaming",
                ],
                ["says NREM shows fast awake-like waves and vivid dreams"],
            ),
        ],
        "REM sleep features rapid eye movements, vivid dreams, wake-like EEG activity, and "
        "skeletal-muscle paralysis. Non-REM (slow-wave) sleep shows slow delta waves and "
        "is deep and restorative with little vivid dreaming.",
    ),
    frq(
        "psych-soc-2-frq6",
        "Describe Selye's General Adaptation Syndrome, naming its three stages in order "
        "and what happens to the body's resources by the final stage.",
        "aamc::psych-soc::stress",
        [
            (
                "Names alarm → resistance → exhaustion, in order.",
                2,
                ["alarm, resistance, exhaustion", "in that order"],
                ["puts the stages out of order", "omits a stage"],
            ),
            (
                "By exhaustion, the body's resources are depleted, raising vulnerability to illness.",
                2,
                [
                    "in exhaustion the body's resources/reserves are depleted",
                    "increased susceptibility to illness or damage",
                ],
                [
                    "says the body is strongest at exhaustion",
                    "says resources are fully restored by the final stage",
                ],
            ),
        ],
        "The General Adaptation Syndrome proceeds alarm → resistance → exhaustion. In the "
        "alarm stage the body mobilizes (fight-or-flight); resistance sustains coping; by "
        "exhaustion the body's resources are depleted, increasing vulnerability to illness.",
    ),
    frq(
        "psych-soc-2-frq7",
        "Define the fundamental attribution error, then contrast it with the self-serving "
        "bias in how each explains behavior.",
        "aamc::psych-soc::attribution",
        [
            (
                "FAE: over-attributing others' behavior to disposition, under-weighting the situation.",
                2,
                [
                    "fundamental attribution error over-emphasizes dispositional causes for others",
                    "under-weights situational factors",
                ],
                [
                    "says the FAE over-emphasizes the situation",
                    "applies the FAE to one's own successes",
                ],
            ),
            (
                "Self-serving bias: crediting one's own successes to disposition, failures to the situation.",
                2,
                [
                    "self-serving bias attributes one's successes to internal factors and failures to external factors"
                ],
                ["reverses the self-serving bias", "conflates it exactly with the FAE"],
            ),
        ],
        "The fundamental attribution error is over-attributing others' behavior to their "
        "character while ignoring the situation. The self-serving bias is attributing "
        "one's own successes to disposition and one's failures to external circumstances.",
    ),
    frq(
        "psych-soc-2-frq8",
        "Two brain structures in the limbic system are the amygdala and the hippocampus. "
        "State the primary function most associated with each.",
        "aamc::psych-soc::biological-behavior",
        [
            (
                "Amygdala: emotion, especially fear/threat processing.",
                2,
                ["amygdala processes emotion, especially fear/threat"],
                [
                    "says the amygdala forms long-term memories (that is hippocampus)",
                    "assigns the amygdala a motor role",
                ],
            ),
            (
                "Hippocampus: formation/consolidation of new long-term (declarative) memories.",
                2,
                [
                    "hippocampus is critical for forming/consolidating new long-term/declarative memories"
                ],
                [
                    "says the hippocampus is the primary fear center",
                    "says the hippocampus controls heart rate",
                ],
            ),
        ],
        "The amygdala processes emotion, especially fear and threat detection. The "
        "hippocampus is essential for forming and consolidating new long-term "
        "(declarative) memories.",
    ),
    frq(
        "psych-soc-2-frq9",
        "Distinguish a caste system from a class system of social stratification with "
        "respect to social mobility.",
        "aamc::psych-soc::social-stratification",
        [
            (
                "Caste: closed, ascribed status at birth, little/no mobility.",
                2,
                [
                    "caste system is closed / status ascribed at birth",
                    "little or no social mobility",
                ],
                [
                    "says caste systems allow free upward mobility",
                    "swaps caste and class",
                ],
            ),
            (
                "Class: more open, achieved status possible, mobility exists.",
                2,
                [
                    "class system is relatively open",
                    "allows social mobility / achieved status",
                ],
                [
                    "says class systems permit no mobility",
                    "defines class as inherited and fixed for life",
                ],
            ),
        ],
        "In a caste system, status is ascribed at birth and the system is closed, allowing "
        "essentially no mobility. In a class system, status can be achieved and the system "
        "is comparatively open, so social mobility is possible.",
    ),
    frq(
        "psych-soc-2-frq10",
        "Describe the demographic transition model's overall trend, contrasting birth and "
        "death rates in the early (pre-industrial) versus late (post-industrial) stages.",
        "aamc::psych-soc::demographics",
        [
            (
                "Early stage: high birth rates AND high death rates (slow/low net growth).",
                2,
                [
                    "early/pre-industrial stage has high birth and high death rates",
                    "little net population growth",
                ],
                ["says the early stage has low birth and low death rates"],
            ),
            (
                "Late stage: low birth AND low death rates (population stabilizes).",
                2,
                [
                    "late/post-industrial stage has low birth and low death rates",
                    "population growth stabilizes/levels off",
                ],
                [
                    "says the late stage has high birth and high death rates",
                    "reverses the trend",
                ],
            ),
        ],
        "The demographic transition moves from high birth and high death rates (slow "
        "growth) in pre-industrial societies, through a phase of falling death rates and "
        "rapid growth, to low birth and low death rates (stable population) in "
        "post-industrial societies.",
    ),
    frq(
        "psych-soc-2-frq11",
        "Contrast labeling theory with strain theory as explanations of deviance, giving "
        "the core cause of deviance each proposes.",
        "aamc::psych-soc::deviance",
        [
            (
                "Labeling theory: deviance results from society labeling an act/person deviant.",
                2,
                [
                    "labeling theory: deviance stems from being labeled deviant by society",
                    "the label shapes identity/behavior",
                ],
                [
                    "says labeling theory locates deviance in blocked goals",
                    "swaps the two theories",
                ],
            ),
            (
                "Strain theory: deviance arises from a gap between cultural goals and legitimate means.",
                2,
                [
                    "strain theory: deviance arises from a mismatch between socially valued goals and access to legitimate means"
                ],
                [
                    "says strain theory is about societal labels",
                    "ignores the goals/means gap",
                ],
            ),
        ],
        "Labeling theory holds that deviance emerges when society labels an act or person "
        "as deviant, and that label reshapes behavior. Strain theory holds that deviance "
        "arises when people lack legitimate means to reach culturally valued goals.",
    ),
    frq(
        "psych-soc-2-frq12",
        "Distinguish ethnocentrism from cultural relativism in how each evaluates another "
        "culture's practices.",
        "aamc::psych-soc::culture",
        [
            (
                "Ethnocentrism: judging another culture by one's own culture's standards.",
                2,
                [
                    "ethnocentrism judges other cultures by one's own standards",
                    "sees one's own culture as superior",
                ],
                [
                    "defines ethnocentrism as judging a culture on its own terms",
                    "swaps the two terms",
                ],
            ),
            (
                "Cultural relativism: understanding a culture on its own terms/standards.",
                2,
                [
                    "cultural relativism evaluates a culture by its own standards/context"
                ],
                ["defines cultural relativism as ranking cultures by one's own values"],
            ),
        ],
        "Ethnocentrism evaluates another culture using the standards of one's own culture, "
        "often treating one's own as superior. Cultural relativism instead seeks to "
        "understand a culture's practices within that culture's own context and standards.",
    ),
    frq(
        "psych-soc-2-frq13",
        "A neuron's resting membrane potential is about −70 mV. Explain what maintains "
        "this negative resting potential, naming the key ion gradient and the pump "
        "involved.",
        "aamc::psych-soc::biological-behavior",
        [
            (
                "Sodium-potassium pump moves 3 Na+ out for 2 K+ in, aiding the gradient (ATP-driven).",
                2,
                [
                    "the Na+/K+ pump moves 3 Na+ out and 2 K+ in",
                    "ATP-driven, contributing to the gradient",
                ],
                [
                    "says the pump moves Na+ in and K+ out",
                    "says resting potential needs no energy/pump at all",
                ],
            ),
            (
                "Membrane is more permeable to K+ at rest; K+ leak leaves the inside net negative.",
                2,
                [
                    "at rest the membrane is most permeable to K+ (K+ leak channels)",
                    "K+ efflux leaves the inside negative (~ −70 mV)",
                ],
                [
                    "says the resting membrane is most permeable to Na+",
                    "says the inside is positive at rest",
                ],
            ),
        ],
        "At rest, the membrane is most permeable to K+, so K+ leaks out and leaves the "
        "inside negative (~ −70 mV). The ATP-driven Na+/K+ pump (3 Na+ out, 2 K+ in) "
        "maintains the ion gradients that sustain this potential.",
    ),
]

# ---------------------------------------------------------------------------
# cars-1  (CARS: 6 humanities, 5 social-sciences = 11)
#
# CARS tests reading/reasoning, not content recall. Each prompt embeds an
# ORIGINAL short excerpt (authored here, no copyrighted text) so the grader can
# judge the student's reasoning from the prompt alone — no MCAT knowledge and no
# external passage needed.
# ---------------------------------------------------------------------------
CARS_1 = [
    frq(
        "cars-1-frq1",
        'Passage: "The restorer who returns a fresco to its original brilliance may '
        "believe she honors the artist, yet in scrubbing away the patina of centuries she "
        "also erases the painting's biography—the smoke, the damp, the clumsy earlier "
        "repairs that are themselves a record of the work's survival. To insist on the "
        "'original' is to choose one moment of a thing's life and pretend it is the "
        "whole.\"\n\nState the author's central claim about art restoration, and explain "
        "the tension the author sees between 'the original' and a work's history.",
        "aamc::cars::humanities",
        [
            (
                "Central claim: restoring a work to its 'original' state erases the historical record it has accumulated.",
                2,
                [
                    "restoration to the original erases/destroys the work's history/biography",
                    "the aging/patina is itself a valuable record",
                ],
                [
                    "says the author fully endorses restoration as honoring the artist",
                    "says aging has no value",
                ],
            ),
            (
                "Tension: the 'original' is just one moment of the work's life, wrongly treated as the whole.",
                2,
                [
                    "the 'original' is only one moment of the object's life",
                    "privileging it ignores the rest of the work's existence",
                ],
                [
                    "says the author sees no tension",
                    "says the whole history equals the original moment",
                ],
            ),
        ],
        "The author argues that restoring a work to its 'original' brilliance destroys the "
        "historical record—the patina, damage, and repairs—that documents its survival. "
        "The tension is that the 'original' is merely one moment in the object's long "
        "life, which restoration wrongly treats as the work's whole identity.",
    ),
    frq(
        "cars-1-frq2",
        "Passage: \"We are told that the new translation is 'accessible,' as though the "
        "reader were an invalid to be spoon-fed. What is lost when difficulty is smoothed "
        'away is precisely the friction that made the original worth the climb."\n\n'
        "Describe the author's attitude toward the 'accessible' translation, and quote a "
        "word or image from the passage that reveals it.",
        "aamc::cars::humanities",
        [
            (
                "Attitude: critical/disapproving of the 'accessible' translation; values difficulty.",
                2,
                [
                    "author is critical/skeptical/disapproving of the accessible translation",
                    "values the difficulty of the original",
                ],
                [
                    "says the author praises the accessible translation",
                    "says the author thinks difficulty is worthless",
                ],
            ),
            (
                "Cites supporting text (e.g. 'spoon-fed'/'invalid' or 'friction'/'climb').",
                2,
                [
                    "quotes/points to 'spoon-fed' or 'invalid' or 'friction' or 'worth the climb'"
                ],
                [
                    "cites no textual evidence",
                    "quotes text unrelated to the author's attitude",
                ],
            ),
        ],
        "The author is critical and disdainful of the 'accessible' translation, believing "
        "it strips away valuable difficulty. Words like 'spoon-fed' and 'invalid' mock the "
        "condescension, while 'friction' and 'worth the climb' show the author prizes the "
        "challenge of the original.",
    ),
    frq(
        "cars-1-frq3",
        'Passage: "Cities that added bike lanes saw cycling rates rise, and planners '
        "concluded the lanes had converted drivers into cyclists. But the earliest "
        "adopters of bike lanes were cities where cycling was already fashionable; the "
        'infrastructure may have followed the demand as much as created it."\n\nIdentify '
        "the assumption in the planners' conclusion that the author challenges, and "
        "explain the alternative causal explanation the author offers.",
        "aamc::cars::social-sciences",
        [
            (
                "Assumption challenged: that the bike lanes CAUSED the rise in cycling.",
                2,
                [
                    "the planners assume the lanes caused/created the increase in cycling",
                    "assumes a cause-and-effect direction",
                ],
                [
                    "says the author accepts the lanes caused the increase",
                    "misidentifies the assumption",
                ],
            ),
            (
                "Alternative: reverse/confounded causation—existing demand drove lane-building.",
                2,
                [
                    "pre-existing cycling demand/popularity led cities to build lanes",
                    "causation may run the other way / cities self-selected",
                ],
                [
                    "offers no alternative explanation",
                    "restates the planners' causal claim as the alternative",
                ],
            ),
        ],
        "The planners assume the bike lanes caused the rise in cycling. The author "
        "challenges that causal direction, noting the lanes appeared first in cities where "
        "cycling was already popular—so pre-existing demand may have driven lane "
        "construction (reverse or confounded causation), not the reverse.",
    ),
    frq(
        "cars-1-frq4",
        "Passage: \"The historian calls the archive 'innocent,' but no archive is "
        "innocent. Someone chose what to keep and what to burn; the silences in the record "
        'are as authored as the documents that remain."\n\nExplain what the author means '
        "by claiming the archive is not 'innocent,' and what the 'silences' refer to.",
        "aamc::cars::humanities",
        [
            (
                "'Not innocent' = the archive is selectively shaped by human choices, not a neutral record.",
                2,
                [
                    "the archive is selectively created/curated by human choices",
                    "not neutral/objective/impartial",
                ],
                [
                    "says the archive is a complete, unbiased record",
                    "says 'innocent' means factually accurate",
                ],
            ),
            (
                "'Silences' = deliberate omissions / what was discarded, which themselves carry meaning.",
                2,
                [
                    "silences are the omissions / what was destroyed or excluded",
                    "these gaps are 'authored' and meaningful",
                ],
                [
                    "says silences are meaningless gaps",
                    "says silences refer to quiet reading rooms or literal silence",
                ],
            ),
        ],
        "Calling the archive 'not innocent' means it is not a neutral record but one shaped "
        "by deliberate choices about what to preserve and what to destroy. The 'silences' "
        "are those omissions—what was burned or left out—which are as intentional and "
        "meaningful as the documents that survive.",
    ),
    frq(
        "cars-1-frq5",
        'Passage: "The researcher argued that remote work reduces employee productivity, '
        "pointing to a drop in measured output at one large firm after it went fully "
        'remote."\n\nThe claim rests on a single firm. Describe one kind of additional '
        "evidence that would most strengthen the general claim, and explain why it would "
        "help.",
        "aamc::cars::social-sciences",
        [
            (
                "Names apt strengthening evidence: the same effect across many/diverse firms, or a controlled comparison.",
                2,
                [
                    "evidence from many/diverse firms showing the same drop",
                    "a controlled comparison / holding other factors constant",
                ],
                [
                    "proposes evidence about only the same single firm",
                    "proposes irrelevant evidence",
                ],
            ),
            (
                "Explains why: broader/controlled data rules out the one firm being unrepresentative or confounded.",
                2,
                [
                    "broader/controlled data supports generalization",
                    "rules out the single firm being a fluke or confounded",
                ],
                [
                    "gives no reason",
                    "reasoning does not connect the evidence to the claim's weakness",
                ],
            ),
        ],
        "The claim would be strengthened by evidence that many diverse firms saw the same "
        "productivity drop after going remote, ideally with a controlled comparison. That "
        "matters because a single firm could be unrepresentative or affected by other "
        "changes; broad, controlled data rules out those alternatives and supports "
        "generalizing the effect to remote work itself.",
    ),
    frq(
        "cars-1-frq6",
        "Passage: \"Great cities are not planned; they accrete. The planner's grid is a "
        "hypothesis about how people should move, but the desire path worn diagonally "
        "across the lawn is the pedestrian's rebuttal—and the pedestrian is always "
        "right.\"\n\nExplain how the image of the 'desire path' functions in the author's "
        "argument about how cities develop.",
        "aamc::cars::humanities",
        [
            (
                "The desire path is evidence/example supporting the claim that cities emerge from actual use.",
                2,
                [
                    "the desire path is an example/evidence for cities arising from use/accretion",
                    "illustrates the central claim",
                ],
                [
                    "treats the desire path as merely decorative with no argumentative role",
                    "says it supports top-down planning",
                ],
            ),
            (
                "It functions as the pedestrian's 'rebuttal' to the planner's grid—use overrides design.",
                2,
                [
                    "it is the pedestrian's rebuttal to the planner's grid",
                    "actual use overrides/wins against the planned design",
                ],
                [
                    "says the grid overrides the desire path",
                    "reverses the author's point",
                ],
            ),
        ],
        "The desire path is the author's key example: a route worn by actual pedestrian "
        "use that contradicts the planner's grid. It functions as concrete evidence for "
        "the thesis that cities 'accrete' from real use rather than being dictated by "
        "top-down design—the pedestrian's 'rebuttal' shows use overrides the plan.",
    ),
    frq(
        "cars-1-frq7",
        'Passage: "A popular theory holds that societies grow more secular as they grow '
        "wealthier. Sweden and Japan, prosperous and largely secular, are offered as "
        'proof."\n\nIdentify the kind of counterexample that would most weaken the '
        "wealth-causes-secularization theory, and explain why it undercuts the argument.",
        "aamc::cars::social-sciences",
        [
            (
                "Counterexample: a wealthy but highly religious society (or a poor but highly secular one).",
                2,
                [
                    "a wealthy society that is highly religious",
                    "or a poor society that is highly secular",
                ],
                [
                    "offers another wealthy secular example (which supports, not weakens)",
                    "proposes an irrelevant counterexample",
                ],
            ),
            (
                "Why it weakens: it breaks the wealth→secularization link, showing wealth isn't sufficient/necessary.",
                2,
                [
                    "it breaks the claimed correlation between wealth and secularization",
                    "shows wealth is not sufficient (or necessary) for secularization",
                ],
                ["gives no reason", "reasoning does not connect to the causal claim"],
            ),
        ],
        "A wealthy society that remains highly religious (or a poor society that is highly "
        "secular) would most weaken the theory. Such a case breaks the claimed link "
        "between wealth and secularization, showing that prosperity is not sufficient to "
        "produce secularization and that the two examples given may be coincidental.",
    ),
    frq(
        "cars-1-frq8",
        "Passage: \"The critic praised the novel for its 'realism,' but realism is a style "
        "like any other—a set of conventions we have merely grown used to and stopped "
        "noticing. A future age will find our realism as mannered as we find the "
        'flourishes of the Baroque."\n\nState a conclusion about the nature of artistic '
        "'realism' that the author would most likely endorse, grounded in the passage.",
        "aamc::cars::humanities",
        [
            (
                "Conclusion: realism is a set of conventions/a style, not a transparent depiction of reality.",
                2,
                [
                    "realism is a style/set of conventions",
                    "not a neutral or transparent window onto reality",
                ],
                [
                    "says the author thinks realism is objectively the truest depiction",
                    "says realism is style-free",
                ],
            ),
            (
                "Grounds it in the passage's logic (conventions we don't notice will later look 'mannered').",
                2,
                [
                    "because unnoticed conventions will later appear mannered/dated, like the Baroque",
                    "realism is historically contingent",
                ],
                [
                    "provides no grounding from the passage",
                    "grounding contradicts the passage",
                ],
            ),
        ],
        "The author would endorse the view that 'realism' is not a neutral depiction of "
        "reality but simply a style—a set of conventions we no longer notice. The passage "
        "grounds this by predicting that a future age will find today's realism as "
        "'mannered' as we find the Baroque, showing realism is historically contingent.",
    ),
    frq(
        "cars-1-frq9",
        'Passage: "Standardized tests promise to measure merit while stripping away '
        "privilege. Yet the child with a tutor, a quiet room, and three practice attempts "
        "arrives at the same exam as the child with none, and we call the gap between "
        "their scores 'ability.'\"\n\nState the author's central argument about "
        "standardized tests, and identify what the author claims the scores actually "
        "reflect.",
        "aamc::cars::social-sciences",
        [
            (
                "Central argument: the tests do NOT fairly/purely measure merit; they reflect privilege.",
                2,
                [
                    "standardized tests do not purely/fairly measure merit or ability",
                    "they reflect privilege/unequal circumstances",
                ],
                [
                    "says the author agrees the tests fairly measure merit",
                    "misses the author's critique",
                ],
            ),
            (
                "Scores reflect unequal resources (tutoring, environment, practice), mislabeled as 'ability.'",
                2,
                [
                    "scores reflect differences in resources/preparation (tutor, quiet room, practice)",
                    "this gap is wrongly called innate 'ability'",
                ],
                [
                    "says the score gap is purely innate ability",
                    "ignores the resource gap the author stresses",
                ],
            ),
        ],
        "The author argues that standardized tests fail to deliver on their promise to "
        "measure merit free of privilege. What the scores actually reflect is unequal "
        "resources—tutoring, a quiet room, repeated practice—which the author says we "
        "mislabel as innate 'ability.'",
    ),
    frq(
        "cars-1-frq10",
        "Passage: \"Museums speak of 'acquiring' their treasures, a gentle word. It covers "
        "purchase and gift, but it also covers the crate pried from a temple wall and "
        "shipped across an ocean under armed guard.\"\n\nExplain the author's purpose in "
        "drawing attention to the word 'acquiring,' and describe the author's stance "
        "toward museum collections.",
        "aamc::cars::humanities",
        [
            (
                "Purpose: to show the neutral word 'acquiring' masks/euphemizes coercive taking (looting).",
                2,
                [
                    "the word 'acquiring' euphemizes / hides coercive or illegitimate taking",
                    "it lumps looting in with purchase and gift",
                ],
                [
                    "says 'acquiring' is used to accurately describe fair purchases only",
                    "misses the euphemism point",
                ],
            ),
            (
                "Stance: critical/skeptical of how (some) museum collections were obtained.",
                2,
                [
                    "author is critical/skeptical of how museums obtained their collections"
                ],
                [
                    "says the author approves of museum acquisition practices",
                    "says the author is neutral/indifferent",
                ],
            ),
        ],
        "The author highlights 'acquiring' to expose it as a euphemism: a gentle word that "
        "quietly covers looting—the crate 'pried from a temple wall'—alongside legitimate "
        "purchase and gift. The author's stance is critical and skeptical of how museums "
        "obtained at least some of their collections.",
    ),
    frq(
        "cars-1-frq11",
        'Passage: "Economists distinguish between risk, where the odds are known, and '
        "uncertainty, where they are not. Most consequential decisions—whom to marry, "
        "which career to enter—belong to the second category, yet we insist on treating "
        "them like the first.\"\n\nUsing the author's risk/uncertainty distinction, "
        "explain which category buying insurance against a common, well-documented hazard "
        "falls into, and justify your classification.",
        "aamc::cars::social-sciences",
        [
            (
                "Correct classification: 'risk' (the odds/probabilities are known).",
                2,
                ["classifies it as risk"],
                ["classifies it as uncertainty", "gives no classification"],
            ),
            (
                "Justification ties to the author's definition (known odds = risk).",
                2,
                [
                    "a well-documented hazard has known/calculable odds, which the author defines as risk"
                ],
                [
                    "justification contradicts the author's definitions",
                    "gives no justification",
                ],
            ),
        ],
        "It falls under 'risk.' The author defines risk as decisions where the odds are "
        "known and uncertainty as those where they are not. A common, well-documented "
        "hazard has calculable probabilities, so insuring against it is a decision made "
        "under known odds—risk, not uncertainty.",
    ),
]

TESTS: dict[str, list] = {
    "bio-biochem-1": BIO_BIOCHEM_1,
    "bio-biochem-2": BIO_BIOCHEM_2,
    "chem-phys-1": CHEM_PHYS_1,
    "chem-phys-2": CHEM_PHYS_2,
    "psych-soc-1": PSYCH_SOC_1,
    "psych-soc-2": PSYCH_SOC_2,
    "cars-1": CARS_1,
}


def write_test(test_id: str, frqs: list) -> None:
    for f in frqs:
        assert f["max_points"] == sum(c["points"] for c in f["rubric"]), f["id"]
    for base in (RES, TS):
        path = base / f"{test_id}.json"
        data = json.loads(path.read_text())
        data["free_response_questions"] = frqs
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")


def main() -> None:
    for test_id, frqs in TESTS.items():
        write_test(test_id, frqs)
        # verify the two copies are byte-identical
        a = (RES / f"{test_id}.json").read_bytes()
        b = (TS / f"{test_id}.json").read_bytes()
        assert a == b, f"{test_id}: copies differ!"
        print(f"{test_id}: wrote {len(frqs)} FRQ (both copies identical)")


if __name__ == "__main__":
    main()
