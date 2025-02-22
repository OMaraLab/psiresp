---
title: 'PsiRESP: calculating RESP charges with Psi4'
tags:
  - Python
  - molecular dynamics
  - atomic partial charges
  - force fields
  - resp
authors:
  - name: Lily Wang
    orcid: 0000-0002-6095-6704
    affiliation: 1
  - name: Megan L. O'Mara^[corresponding author]
    orcid: 0000-0002-8764-1585
    affiliation: 1
affiliations:
 - name: Research School of Chemistry, College of Science, Australian National University, Canberra, ACT, 2601, Australia
   index: 1
date: 16 December 2021
bibliography: paper.bib
---



# Summary

Molecular dynamics (MD) simulations study the movement of particles over time, and have become a fundamental tool in biomedical and materials research. The accuracy of a MD simulation depends on its ability to model the physics of the chosen system, a capacity that arises from the parameters used to model the interactions between atoms (also known as a “force field”). The functional form of most force fields is an approximation of real word physics to allow for tractable simulation; one common simplification is to model the dynamic distribution of electrons around an atom as single, static, fixed partial charge. Electrostatic interactions between non-bonded atoms can then be simplified to pairwise interactions between the partial charges.

PsiRESP is a Python package that uses the Psi4 quantum chemistry engine to calculate atomic partial charges. It supports multiple methods, each based on the electrostatic potential experienced at particular grid points around the molecule. These partial charges can then be used in MD simulations.

# Background

A number of methods have been developed to generate molecular partial charges, and results vary widely between each method. Approaches based on quantum mechanics (QM) calculations are particularly advantageous for novel compounds, as no knowledge beyond the molecular structure is required. One common approach is to find per-atom charges that reproduce the electrostatic potential outside the molecular surface. Methods following this design include the simply named "ESP" model, the restrained ESP ("RESP") model, and the "RESP2" model.

## ESP

The electrostatic potential $V$ is the potential generated by the nuclei and electrons in a molecule. At any point in space $r$, it is:
$$V(\vec{r}) = \sum_{n=1}^{nuclei} \frac{Z_n}{|\vec{r} - \vec{R}_n|} - \int \frac{\rho(\vec{r’})}{|\vec{r} - \vec{r’}|} d\vec{r}$$

The “ESP” method published by Singh and Kollman in 1984 [@singh1984] evaluates the electrostatic potential on a grid of points around the molecule. This method canonically uses the HF/6-31G* level of theory in the gas phase. The approach is still used by the Automated Topology Builder [@malde2011] to derive charges for GROMOS, although the ATB method uses B3LYP/6-31G* in implicit solvent.

One flaw of the ESP method is that it is difficult to distinguish the contribution of buried atoms within the molecule to the electrostatic potential at the surface.  As a result, the charges assigned to the buried atoms can vary substantially with minor changes in geometry. 

## RESP

The restrained electrostatic potential (RESP) [@bayly1993; @cornell1993; @cieplak1995] approach introduces a hyperbolic restraint towards 0, penalizing charges with high magnitudes. This is intended to reduce overfitting and hence the variation between charges, resulting in charges that are more easily transferable between molecules and less conformationally dependent. The function follows the form:

$$\chi_{penalty} = a\sum_{n=1}^{nuclei} ((q_{n}^{2} + b^2)^{1/2} – b)$$

$a$ defines the asymptotic limits of the penalty, while $b$ controls its width, or its degree of curvature at the minimum. $b$ is typically set to 0.1 e. In a two-stage fit, $a$ is usually tightened (increased) in the second stage. The standard values are 0.0005 au for the first stage, and 0.001 for the second stage. Hydrogens are often excluded in the hyperbolic penalty. Two-stage RESP is the typical charge model employed by the AMBER and GLYCAM force fields.

As with the ESP method, RESP typically computes the electrostatic potential at HF/6-31G* in the gas phase.

## RESP2

The HF/6-31G* level of theory commonly used for RESP charge derivation overestimates the gas-phase polarity of molecules [@carlson1993]. The recently published RESP2 [@schauperl2020] addresses this issue by using a higher level of QM theory (PW6B95/aug-cc-pV(D + d)Z), as well as combining charges fitted to both gas- and aqueous-phase data. While optimising charge parameters alone without modifying Lennard-Jones parameters may not increase the accuracy of simulations [@mobley2007], both parameters can be co-optimised for greater accuracy. 

## Existing tools

Several tools already exist for fitting ESP-based charges. The canonical program is `resp` [@bayly1993], written in FORTRAN and distributed by the AmberTools package [@case]. However, using this with multiple molecules is a tedious and manual process. As the charge distribution of a molecule is highly dependent on its conformation, it is often necessary to examine multiple conformers and orientations of a molecule to obtain a general charge distribution that can be used to derive atomic partial charges [@reynolds1992]. In order to use the `resp` program, different conformers and orientations must be manually generated, individual QM jobs generated for each, and then data converted into the RESP format. Constraints are manually specified on multiple rows, which requires significant effort to input manually and is difficult to read and verify.

The online R.E.D. Tools (RESP and ESP charge Derive) [@dupradeau2007; @dupradeau2010] provide a much more accessible interface to the `resp` tool. It supports quantum chemistry jobs using both the Gaussian [@gaussian] and GAMESS [@gamess] QM engines, as well as both CHELPG [@breneman1990] and Connolly [@connolly1983] surfaces. Users can furthermore specify intramolecular and intermolecular charge constraints and charge equivalence constraints. The R.E.D. Tools use the canonical ``resp`` program for the actual charge fitting. However, conformer geometries must be provided by the user, and re-orientations of each conformer manually specified. Molecules must be provided in a specialized P2N format, and it is strongly recommended that a human user check each file before submission. Moreover, while standalone tools can be downloaded and run, full functionality is only available for jobs submitted to the server.

Finally, a Python RESP plugin for Psi4 also exists [@alenaizan2020]. Also called ``resp``, the plugin implements the RESP scheme but does not allow for intermolecular constraints. Intermolecular constraints are necessary for parametrising the atomic partial charges of multiple molecules (e.g. connected residues in a polymer) in tandem, so this poses a significant limitation for such goals. As with the canonical resp and the R.E.D. tools, all geometries must be specified by the user.

# Statement of Need

PsiRESP is a Python package that can be used to calculate ESP and RESP charges, as well as the next-generation RESP2 scheme. Both intra-molecular and inter-molecular charge constraints and charge equivalence constraints are supported. Users may generate their own conformers of a molecule, or conformers can be automatically generated. Multiple orientations can also be specified or automatically generated for each conformer, to ensure a generally applicable distribution of charges. Multiple atomic radii sets are supported, including the Bondi and Merz-Singh-Kollman sets of radii.

The automated conformer generation enables computing more transferrable charges with fewer resources. Conformers are generated following the Electrostatically Least-interacting Functional groups method (ELF). Here, a pool of conformers is ranked by the electrostatic interaction between functional groups; the least-interacting conformers are selected; and then a user-specified number of final conformers is chosen from the secondary pool to maximise structural diversity (by the root mean square deviation of coordinates). This allows even a small number of conformers to cover a breadth of structural range.

*Intra*-molecular charge constraints, or charge constraints that only apply to one molecule, are useful for enforcing equivalent charges between symmetric groups. For example, these are used to symmetrize the charges of hydrogens around a methyl or methylene group. They also allow for computing charges for a molecule that is compatible with an existing environment. One use case is calculating the charges of a non-canonical amino acid (ncAA) in a protein where the charges of canonical residues are already known; here, it is general practice to constrain the charges on the backbone of the ncAA to equal the known charges of the backbone in other residues.

*Inter*-molecular charge constraints, or charge constraints that apply to multiple molecules, are particularly useful for computing the charges of multiple components of a single macromolecule. For example, a co-polymer can be comprised of multiple monomer species, A and B. In order to calculate suitable charges for each monomer, their surrounding environment (the adjacent monomers) must be taken into account. However, the same monomer may be multiple different local environments: AAA, AAB, or BAB. Without charge constraints, the charges calculated for monomer A may differ between different environments, which lowers the transferability of the charge set for creating new polymers. Inter-molecular charge constraints can be applied to constrain the charges of a particular monomer across all environments to be equivalent, ensuring that the derived charges can be used transferrably. 

The ability to serialize and deserialize a job or molecule to or from JSON also enables easy transferrability between machines, as well as documentation of the parameters used to generate charges. The multiple converters to other libraries (currently supported outputs are an MDAnalysis universe [@michaud-agrawal2011; @gowers2016] and an OpenForceField toolkit-compatible [@openff-toolkit] RDKit [@rdkit] molecule) allow for further work, or additional options to write to different formats.

# Functionality

PsiRESP uses QCElemental [@qcelemental] and RDKit to parse molecular input and output, meaning that it supports a wide array of formats, including XYZ and SMILES. A strict limitation is that elements must be given; bond connectivity must also be present, or inferrable by proximity. Conformers are embedded and generated using RDKit. Quantum chemistry calculations are run in Psi4 [@psi4]. 

PsiRESP can be used interactively in a single job in connection with a QCFractal [@qcfractal] server. Alternatively, in acknowledgement of possible limits on time or other computing resources, users can use PsiRESP in two stages: first to generate input files for Psi4 that users can run manually or in parallel job submissions, and secondly to read the data computed from each file to finish the charge calculations.

The project contains a thorough Continuous Integration test suite ensuring that charges are comparable with those derived from other similar packages and previous versions. Code is written in a modular style, allowing for easy extension of capabilities, e.g. including charges computed from electric fields in the future, or using other QM engines. Core dependencies have been kept as minimal as possible to ease installation, although users are encouraged to make use of other packages (e.g. MDAnalysis or the OpenForceField toolkit for additional I/O and functionality). PsiRESP can be installed via `pip` and `conda`. Releases follow Semantic Versioning 2.0.

# Acknowledgements

This work was supported by a grant from the Australian Research Council (DP180103573). This project is based on the Computational Molecular Science Python Cookiecutter version 1.2. Pre-configured models and reorientation algorithm are written to directly match results from RESP ESP charge Derive (R.E.D.) [@dupradeau2007; @dupradeau2010]. ATBRESP tries to match results from Automated Topology Builder. RESP2 tries to match results from RESP2. Some tests compare results to output from resp, the current RESP plugin for Psi4. The research was undertaken with the assistance of resources and services from the National Computational Infrastructure (NCI), which is supported by the Australian Government.


# References