import copy
import os

from promethium_sdk.utils import base64encode
from promethium_sdk.client import PromethiumClient
from promethium_sdk.models import (
    CreateConformerSearchWorkflowRequest,
)

# This example expects that your API Credentials have been configured and
# stored in a .promethium.ini file
# If that hasn't been completed, for instructions see:
# https://github.com/qcware/promethium-examples/tree/main#configuring-your-api-credentials

# Est. Runtimes:
# Wall-clock / Real-world time:
# Diethyl Ether = <5 mins
# Nirmatrelvir = <20 mins
#
# Billable compute time:
# Diethyl Ether = <5 mins
# Nirmatrelvir = ~65 mins
#
# Note: Parameters have been modified from the default to reduce compute time
# Without modification from default, est. billable compute time for
# Nirmatrelvir is ~4.5 hours


foldername = "output"
base_url = os.getenv("PM_API_BASE_URL", "https://api.promethium.qcware.com")
gpu_type = os.getenv("PM_GPU_TYPE", "a100")

if not os.path.exists(foldername):
    os.makedirs(foldername)

# Specify the input SMILES string(s)
# Example is extensible to additional SMILES strings: apply the same format
# for subsequent SMILES strings
SMILES = [
    "CCOCC",  # Diethyl Ether
    "CC1(C2C1C(N(C2)C(=O)C(C(C)(C)C)NC(=O)C(F)(F)F)C(=O)NC(CC3CCNC3=O)C#N)C",  # Nirmatrelvir
]

# Specify the names of the SMILES string(s)
SMILES_Names = [
    "Diethyl_Ether",
    "Nirmatrelvir",
]

# Conformer Search (CS) Workflow Configuration
job_params = {
    "name": "name_placeholder",
    "version": "v1",
    "kind": "ConformerSearch",
    "parameters": {
        "molecule": {},
        "params": {
            "confgen_max_n_conformers": 50,
            "confgen_rmsd_threshold": 0.3,
            "charge": 0,
            "multiplicity": 1,
        },
        "filters": [
            {
                "filtertype": "ForceField",
                "params": {
                    "do_geometry_optimization": True,
                    "forcefield_type": "MMFF",
                    "max_n_conformers": 50,
                    "energy_threshold": 15,
                    "rmsd_threshold": 0.3,
                    "coulomb_distance_threshold": 0.005
                },
                "key": "FF"
            },
            {
                "filtertype": "ANI",
                "params": {
                    "max_n_conformers": 10,
                    "energy_threshold": 10,
                    "distance_threshold": 0.005,
                    "do_geometry_optimization": True
                },
                "key": "ANI"
            },
            {
                "filtertype": "DFT",
                "params": {
                    "maxiter": 15,
                    "energy_threshold": 5,
                    "do_geometry_optimization": True,
                    "distance_threshold": 0.005,
                    "g_thresh": 1e-4
                },
                "system": {
                    "params": {
                        "basisname": "def2-svp",
                        "jkfit_basisname": "def2-universal-jkfit",
                        "methodname": "b3lyp-d3",
                        "xc_grid_scheme": "SG1",
                        "pcm_epsilon": 80.4,
                        "pcm_spherical_npoint": 110
                    }
                },
                "hf": {
                    "params": {
                        "g_convergence": 0.000001
                    }
                },
                "jk_builder": {
                    "type": "core_dfjk",
                    "params": {}
                },
                "key": "DFT Stage 1 (Coarse Filtering)"
            },
        ],
    },
    "resources": {"gpu_type": "a100"},
}

# Instantiate the Promethium client and submit a CS workflow for each SMILES string
# using the above configuration
prom = PromethiumClient()
workflow_ids = []
# For each SMILES string, set the workflow name and input string in the configuration:
for smile, smile_name in zip(SMILES, SMILES_Names):
    tmp_job_params = copy.deepcopy(job_params)
    tmp_job_params["name"] = f"{smile_name}_api_conformer-search"
    tmp_job_params["parameters"]["molecule"] = {
        "base64data": base64encode(smile),
        "filetype": "smi",
    }
    payload = CreateConformerSearchWorkflowRequest(**tmp_job_params)
    workflow = prom.workflows.submit(payload)
    workflow_ids.append(workflow.id)
    print(f"Workflow {workflow.name} submitted with id: {workflow.id}")


# Optional step to wait for all workflows to complete and then download and print the results
# It often makes sense to decouple the submission script from the results
# generation script. That way, the submission script can run,
# generate the workflow ids (store them), and then the results generation script
# can be run at a later time (and re-run if there are bugs).
# This is especially useful if you are running many workflows.
# However, for simplicity, we include the wait and results generation in the same script.

# For each Conformer Search
for workflow_id in workflow_ids:
    # Wait for the workflow to finish
    prom.workflows.wait(workflow_id)

    # Get the status and Wall-clock time:
    workflow = prom.workflows.get(workflow_id)
    print(f"Workflow {workflow.name} completed with status: {workflow.status}")
    print(f"Workflow completed in {workflow.duration_seconds:.2f}s")

    # Obtain the numeric results:
    cs_results = prom.workflows.results(workflow_id)
    with open(f"{foldername}/{workflow.name}_results.json", "w") as fp:
        fp.write(cs_results.model_dump_json(indent=2))

    # Extract and print the geometries and energies for each conformer
    # contained in the numeric results:
    conformers = cs_results.get_artifact("conformers")
    print("Conformers:\n====================\n")
    print(conformers)
