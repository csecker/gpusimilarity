"""
These are utilities used for generating fingerprints and images.  This
implementation is RDKit-specific, using Morgan fingerprints, but it should be
trivial to change out both fingerprint and imagine generation and have all
down-stream applications use your preferred method.

NOTE:  You can speed up fingerprint creation using ipyparallel
To do this, it requires a virtualenv with ipyparallel installed
(via pip).  After sourcing the virtualenv, you can then create DBs with:
    python3 gpusim_createdb.py input.smi
YOU MUST START ipcluster from vcs-src/gpusim/python
"""

from PyQt5 import QtCore

from rdkit import Chem, DataStructs
from rdkit.Chem import Draw
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Avalon import pyAvalonTools

# NOTE:  GPGPU backend requires fingerprint size to be sizeof(int) divisible
BITCOUNT = 1024


def add_fingerprint_bin_to_smi_line(line, fingerprint='Morgan', trust_smiles=False):
    splitl = line.strip().split()
    try:
        smiles, cid = splitl[:2]
    except ValueError:
        raise ValueError(splitl)
    try:
        fp_binary, canon_smiles = smiles_to_fingerprint_bin(smiles, fingerprint,
                                                trust_smiles=trust_smiles) #noqa
    except RuntimeError:
        print(f"Error processing: '{line}'")
        return None

    return (canon_smiles, cid, fp_binary)


def split_lines_add_fp(lines, fingerprint='Morgan', dview=None, trust_smiles=False):
    def per_line_func(line):
        return add_fingerprint_bin_to_smi_line(line, fingerprint, trust_smiles=trust_smiles)

    map_func = dview.map_sync if dview else map
    return map_func(per_line_func, lines)


def compress_qbas(qba_list, dview=None):
    if dview is not None:
        return dview.map_sync(QtCore.qCompress, qba_list)
    else:
        return map(QtCore.qCompress, qba_list)


def smiles_to_fingerprint_bin(smiles, fingerprint='Morgan', trust_smiles=False, query=False):
    mol = Chem.MolFromSmiles(smiles, sanitize=(not trust_smiles))
    if mol is None:
        raise RuntimeError("Bad structure")
    if trust_smiles:
        mol.UpdatePropertyCache()
        Chem.FastFindRings(mol)
    if fingerprint == "Morgan":
        fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, BITCOUNT)
    if fingerprint == "RDKit":
        rdkgen = rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=BITCOUNT)
        fp = rdkgen.GetFingerprint(mol)
    if fingerprint == "AtomPairs":
        apgen = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=BITCOUNT)
        fp = apgen.GetFingerprint(mol)
    if fingerprint == "TopologicalTorsions":
        ttgen = rdFingerprintGenerator.GetTopologicalTorsionGenerator(fpSize=BITCOUNT)
        fp = ttgen.GetFingerprint(mol)
    if fingerprint == "Avalon":
        fp = pyAvalonTools.GetAvalonFP(mol, BITCOUNT, isQuery=query)
    canon_smiles = Chem.MolToSmiles(mol)
    canon_smiles = str.encode(canon_smiles)
    return DataStructs.BitVectToBinaryText(fp), canon_smiles


def smiles_to_image_file(smiles, path):
    mol = Chem.MolFromSmiles(smiles)
    Draw.MolToFile(mol, path)
