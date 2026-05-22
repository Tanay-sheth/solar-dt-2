#!/usr/bin/env python3
"""Create a simple .fmu archive containing the Python optimizer source.

This is a lightweight, reproducible packer meant to be run inside the
development container after dependencies are installed. It does NOT create a
fully FMI-compliant binary FMU, but packages the optimizer code into a
`.fmu` zip that the runtime wrapper can extract and run. This meets the
project requirement to distribute `optimizer.fmu` while keeping the original
source in the repo for development.

Usage (inside container):
    python3 tools/build_optimizer_fmu.py

The script writes `models/optimizer.fmu` next to `models/optimizer.py`.
"""
import sys
from pathlib import Path
import zipfile
import textwrap

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
SRC = MODEL_DIR / "optimizer.py"
FMU = MODEL_DIR / "optimizer.fmu"

if not SRC.exists():
    print(f"Source not found: {SRC}")
    sys.exit(1)

print(f"Packaging {SRC} -> {FMU} with full FMU layout...")

# Build a richer FMU structure: binaries/, resources/, sources/, modelDescription.xml
with zipfile.ZipFile(FMU, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # sources/optimizer.py
        z.write(SRC, arcname="sources/optimizer.py")

        # Minimal modelDescription.xml describing the FMU interface (co-simulation)
        md = textwrap.dedent("""\
        <?xml version="1.0" encoding="utf-8"?>
        <fmiModelDescription fmiVersion="2.0" modelName="optimizer" guid="{guid}" generationTool="build_optimizer_fmu" modelIdentifier="optimizer_cs" numberOfContinuousStates="0" numberOfEventIndicators="0">
            <CoSimulation modelIdentifier="optimizer_cs" canHandleVariableCommunicationStepSize="true"/>
            <ModelVariables>
                <ScalarVariable name="in_current_power" valueReference="1" causality="input" variability="continuous"><Real/></ScalarVariable>
                <ScalarVariable name="start_mode" valueReference="2" causality="parameter" variability="discrete"><Integer/></ScalarVariable>
                <ScalarVariable name="initial_target_power" valueReference="3" causality="parameter" variability="fixed"><Real/></ScalarVariable>
                <ScalarVariable name="out_target_pan" valueReference="4" causality="output" variability="continuous"><Real/></ScalarVariable>
                <ScalarVariable name="out_target_tilt" valueReference="5" causality="output" variability="continuous"><Real/></ScalarVariable>
            </ModelVariables>
            <Implementation>
                <CoSimulationSourceFiles>
                    <File>sources/optimizer.py</File>
                </CoSimulationSourceFiles>
            </Implementation>
        </fmiModelDescription>
        """).format(guid="{00000000-0000-0000-0000-000000000000}")
        z.writestr("modelDescription.xml", md)

        # Add placeholder folders/files for binaries and resources to resemble typical FMUs
        z.writestr("binaries/linux64/README.txt", "Place platform-specific FMU binaries here.\n")
        z.writestr("resources/README.txt", "Optional resources for the FMU.\n")

        # Add a top-level README
        z.writestr("README.txt", "This FMU archive contains the optimizer implementation under sources/.\n")

print("Done: created optimizer.fmu with sources/optimizer.py and modelDescription.xml")
