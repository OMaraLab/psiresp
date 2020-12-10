import itertools
import os
from collections import defaultdict
import functools

import pandas as pd
import psi4
import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem, rdFMCS

from . import vdwradii


def rdmol_to_psi4mols(rdmol, name=None):
    confs = rdmol.GetConformers()
    n_atoms = rdmol.GetNumAtoms()
    atoms = [rdmol.GetAtomWithIdx(i) for i in range(n_atoms)]
    symbols = [a.GetSymbol() for a in atoms]
    ATOM = "{sym} {x[0]} {x[1]} {x[2]}"

    if name is None:
        name = "Mol"
    
    mols = []

    for i, c in enumerate(confs, 1):
        pos = c.GetPositions()
        xyz = [ATOM.format(sym=a, x=x) for a, x in zip(symbols, pos)]
        txt = f"{n_atoms}\n{name}_c{i}\n" + "\n".join(xyz)
        mol = psi4.core.Molecule.from_string(txt, dtype="xyz")
        mols.append(mol)
    
    return mols


def psi4mol_to_rdmol(mol):
    txt = mol.format_molecule_for_mol()
    return Chem.MolFromMol2Block(txt)


def rdmols_to_inter_chrequiv(rdmols, n_atoms=4):
    matches = set()
    for pair in itertools.combinations(rdmols, 2):
        res = rdFMCS.FindMCS(pair,
                             # TODO: AtomCompare.CompareIsotopes?
                             atomCompare=rdFMCS.AtomCompare.CompareElements,
                             bondCompare=rdFMCS.BondCompare.CompareOrderExact,
                             matchValences=True,
                             ringMatchesRingOnly=True,
                             completeRingsOnly=True,
                             timeout=1)
        if not res.canceled and res.numAtoms >= n_atoms:
            matches.add(res.smartsString)
    
    submols = [Chem.MolFromSmarts(x) for x in matches]
    chrequiv = []
    for ref in submols:
        sub = []
        for n in range(ref.GetNumAtoms()):
            sub.append(set())
        for j, mol in enumerate(rdmols):
            subs = mol.GetSubstructMatches(ref)
            for k, atoms in enumerate(subs):
                sub[k] |= set([(j, x) for x in atoms])
        for cmp in sub:
            for k, group in enumerate(chrequiv):
                if len(group and cmp):
                    group.update(cmp)
                    break
            else:
                chrequiv.append(cmp)
    
    return [list(x) for x in chrequiv]


def iterable(obj):
    """Returns ``True`` if `obj` can be iterated over and is *not* a  string
    nor a :class:`NamedStream`"""
    if isinstance(obj, str):
        return False  # avoid iterating over characters of a string

    if hasattr(obj, 'next'):
        return True  # any iterator will do
    try:
        len(obj)  # anything else that might work
    except (TypeError, AttributeError):
        return False
    return True


def asiterable(obj):
    """Returns `obj` so that it can be iterated over.

    A string is *not* detected as and iterable and is wrapped into a :class:`list`
    with a single element.

    See Also
    --------
    iterable

    """
    if not iterable(obj):
        obj = [obj]
    return obj


def read_csv(path):
    return pd.read_csv(path, index_col=0, header=0)


def try_load_data(path, force=False, verbose=False):
    suffix = path.split(".")[-1]

    if not force:
        if suffix == 'csv':
            loader = read_csv
        elif suffix in ('dat', 'txt'):
            loader = np.loadtxt
        elif suffix in ('npy', 'npz'):
            loader = np.load
        else:
            raise ValueError(f"Can't find loader for {suffix} file")
        
        try:
            data = loader(path)
        except:
            if verbose:
                print(f'Could not load data from {path}: rerun(ning).')
        else:
            if verbose:
                print(f'Loaded from {path}.')
                return data, path
    return None, path


def save_data(data, path, comments=None, verbose=False):
        suffix = path.split('.')[-1]
        if suffix == 'csv':
            data.to_csv(path)
        elif suffix in ('dat', 'txt'):
            np.savetxt(path, data, comments=comments)
        elif suffix == 'npy':
            np.save(path, data)
        elif suffix == 'npz':
            np.savez(path, **data)
        else:
            raise ValueError(f"Can't find saver for {suffix} file")
        if verbose:
            print('Saved to', path)


def cached(func):
    """
    Cache the output of functions so they appear as properties.
    
    Adapted from MDAnalysis. Definitely want to replace this with
    functools.cached_property when we can guarantee python >= 3.8.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        key = func.__name__[4:]
        try:
            return self.__dict__[key]
        except KeyError:
            self.__dict__[key] = ret = func(self, *args, **kwargs)
            return ret

    return property(wrapper)


    
def datafile(func):
    """Try to load data from file. If not found, saves data to same path"""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        filename = self.name + "_" + func.__name__[4:] + ".dat"
        data, path = try_load_data(filename, force=self.force,
                                   verbose=self.verbose)
        if data is not None:
            return data

        data = func(self, *args, **kwargs)
        
        comments = None
        if path.endswith('npy'):
            try:
                data, comments = data
            except ValueError:
                pass
        save_data(data, path, comments=comments,
                    verbose=self.verbose)
        return data
    return wrapper


    

def rotate_x(n, coords):
    """
    Rotate coordinates such that the ``n``th coordinate of
    ``coords`` becomes x-axis.

    Adapted from R.E.D. in perl.

    Parameters
    ----------
    n: int
        index of coordinates
    coords: ndarray
        coordinates
    """
    x, y, z = coords[n]
    hypotenuse = np.sqrt(y**2 + z**2)
    adjacent = abs(y)
    angle = np.arccos(adjacent/hypotenuse)

    if z >= 0:
        if y < 0:
            angle = np.pi - angle
    else:
        if y >= 0:
            angle = 2 * np.pi - angle
        else:
            angle = np.pi + angle

    cos_angle = np.cos(angle)
    sin_angle = np.sin(angle)
    ys = coords[:, 1].copy()
    zs = coords[:, 2].copy()
    coords[:, 1] = zs*sin_angle + ys*cos_angle
    coords[:, 2] = zs*cos_angle - ys*sin_angle


def rotate_z(n, coords):
    """
    Rotate coordinates such that the ``n``th coordinate of
    ``coords`` becomes z-axis.

    Adapted from R.E.D. in perl.

    Parameters
    ----------
    n: int
        index of coordinates
    coords: ndarray
        coordinates
    """
    x, y, z = coords[n]
    hypotenuse = np.sqrt(x**2 + y**2)
    adjacent = abs(x)
    angle = np.arccos(adjacent/hypotenuse)

    if y >= 0:
        if x < 0:
            angle = np.pi - angle
    else:
        if x >= 0:
            angle = 2 * np.pi - angle
        else:
            angle = np.pi + angle

    cos_angle = np.cos(angle)
    sin_angle = np.sin(angle)
    xs = coords[:, 0].copy()
    ys = coords[:, 1].copy()
    coords[:, 0] = xs*cos_angle + ys*sin_angle
    coords[:, 1] = ys*cos_angle - xs*sin_angle


def orient_rigid(i, j, k, coords):
    """
    Rigid-body reorientation such that the ``i`` th coordinate
    is the new origin; the ``j` `th coordinate defines the new 
    x-axis; and the ``k`` th coordinate defines the XY plane.

    ``i``, ``j``, and ``k`` should all be different. They are 
    indexed from 0.

    Adapted from R.E.D. in perl.

    Parameters
    ----------
    i: int
        index. Must be different to ``j`` and ``k``
    j: int
        index. Must be different to ``i`` and ``k``
    k: int
        index. Must be different to ``i`` and ``j``
    coords: ndarray
        coordinates

    Returns
    -------
    coordinates: ndarray
        Re-oriented coordinates
    """
    xyz = coords.copy()
    vec = coords[i]
    xyz -= vec
    rotate_x(j, xyz)
    rotate_z(j, xyz)
    rotate_x(k, xyz)
    return xyz


def rotate_rigid(i, j, k, coords):
    """
    Rigid-body rotation such that the ``i`` th and ``j`` th coordinate 
    define a vector parallel to the x-axis; and the ``k`` th coordinate 
    defines a plane parallel to the XY plane.

    ``i`` , ``j`` , and ``k`` should all be different. They are 
    indexed from 0.

    Adapted from R.E.D. in perl.

    Parameters
    ----------
    i: int
        index. Must be different to ``j`` and ``k``
    j: int
        index. Must be different to ``i`` and ``k``
    k: int
        index. Must be different to ``i`` and ``j``
    coords: ndarray
        coordinates

    Returns
    -------
    coordinates: ndarray
        Rotated coordinates
    """
    vec = coords[i].copy()
    xyz = orient_rigid(i, j, k, coords)
    xyz += vec
    return xyz


def scale_radii(symbols, scale_factor, vdw_radii={}, use_radii='msk'):
    """
    Scale van der Waals' radii

    Parameters
    ----------
    symbols: set
        set of element symbols for each atom
    scale_factor: float
    use_radii: str (optional)
        which set of van der Waals' radii to use
    vdw_radii: dict (optional)
        van der Waals' radii. If elements in the molecule are not
        defined in the chosen ``use_radii`` set, they must be given here.

    Returns
    -------
    radii: dict
        scaled radii
    """

    radii = {}
    vdw_set = vdwradii.options[use_radii.lower()]
    for x in symbols:
        try:
            r = vdw_radii.get(x, vdw_set[x])
        except KeyError:
            err = ('{} is not a supported element. Pass in the '
                   'radius in the ``vdw_radii`` dictionary.')
            raise KeyError(err.format(x))
        else:
            radii[x] = r*scale_factor
    return radii


def gen_unit_sphere(n):
    """
    Get coordinates of n points on a unit sphere. 

    Adapted from GAMESS.

    Parameters
    ----------
    n: int
        maximum number of points

    Returns
    -------
    coordinates: np.ndarray
        cartesian coordinates of points
    """
    pi = np.pi
    n_lat = int((pi*n)**0.5)
    n_long = int((n_lat/2))
    fi = np.arange(n_long+1)*pi/n_long
    z, xy = np.cos(fi), np.sin(fi)
    n_horiz = (xy*n_lat+1e-10).astype(int)
    n_horiz = np.where(n_horiz < 1, 1, n_horiz)
    # get actual points
    dots = np.empty((sum(n_horiz), 3))
    dots[:, -1] = np.repeat(z, n_horiz)
    XY = np.repeat(xy, n_horiz)
    fjs = np.concatenate([2*pi*np.arange(j)/j for j in n_horiz])
    dots[:, 0] = np.cos(fjs)*XY
    dots[:, 1] = np.sin(fjs)*XY
    return dots[:n]


def gen_connolly_spheres(symbols, radii, density=1.0):
    """
    Compute Connolly spheres of specified radii and density around each atom.

    Parameters
    ----------
    symbols: iterable
        array of element symbols for each atom
    radii: dict
        scaled radii of elements
    density: float (optional)
        point density

    Returns
    -------
    points: ndarray
        cartesian coordinates of points
    radii: ndarray
        array of radii of each atom
    """
    rad_arr = np.array([radii[z] for z in symbols])
    rads, inv = np.unique(rad_arr, return_inverse=True)
    n_points = ((rads**2)*np.pi*4*density).astype(int)
    points = [gen_unit_sphere(n)*r for n, r in zip(n_points, rads)]
    all_points = [points[i] for i in inv]  # memory?
    return all_points, rad_arr


def gen_connolly_shells(symbols, vdw_radii={}, use_radii='msk',
                        scale_factors=(1.4, 1.6, 1.8, 2.0),
                        density=1.0):
    """
    Generate Connolly shells for each scale factor for each atom.

    Parameters
    ----------
    symbols: iterable
        array of element symbols for each atom
    use_radii: str (optional)
        which set of van der Waals' radii to use
    scale_factors: iterable of floats (optional)
        scale factors
    density: float (optional)
        point density
    vdw_radii: dict (optional)
        van der Waals' radii. If elements in the molecule are not
        defined in the chosen ``use_radii`` set, they must be given here.

    Returns
    -------
    vdw_points: list
    """
    symbol_set = set([x.capitalize() for x in symbols])
    vdw_points = []
    for sf in scale_factors:
        radii = scale_radii(symbol_set, sf, use_radii=use_radii, vdw_radii=vdw_radii)
        shell = gen_connolly_spheres(symbols, radii, density=density)
        vdw_points.append(shell)
    return vdw_points


def gen_vdw_surface(points, radii, coordinates, rmin=0, rmax=-1):
    """
    Compute van der Waals surface in angstrom.

    Parameters
    ----------
    points: ndarray (n_atoms, 3)
        Cartesian coordinates of unit shells for each atom
    radii: ndarray (n_atoms,)
        Scaled van der Waals' radii of each atom
    coordinates: ndarray (n_atoms, 3)
        Cartesian coordinates of each atom
    rmin: float (optional)
        inner boundary of shell to keep grid points from
    rmax: float (optional)
        outer boundary of shell to keep grid points from. If < 0,
        all points are selected.

    Returns
    -------
    surface_points: ndarray  (n_points, 3)
        Cartesian coordinates in angstrom
    """
    if rmax < 0:
        rmax = np.inf
    if rmax < rmin:
        raise ValueError('rmax must be equal to or greater than rmin')

    if len(points) != len(coordinates):
        err = ('Length of ``points`` must match length of ``coordinates``'
               'Generate unit shells for atoms with gen_connolly_shells()')
        raise ValueError(err)
    if len(radii) != len(coordinates):
        err = ('Length of ``radii`` must match length of ``coordinates``'
               'Generate scaled radii for atoms with gen_connolly_shells()')
        raise ValueError(err)

    radii = np.asarray(radii)
    indices = np.arange(radii.shape[0])
    inner = radii*rmin
    inner = np.where(inner < radii, radii, inner)
    outer = radii*rmax

    surface_points = []
    for i, (dots, xyz) in enumerate(zip(points, coordinates)):
        shell = dots+xyz
        mask = indices != i
        a = np.tile(coordinates[mask], (len(dots), 1, 1))
        b = np.tile(shell.reshape(-1, 1, 3), (1, len(radii)-1, 1))
        dist = np.linalg.norm(a-b, axis=2)
        bounds = (dist >= inner[mask]) & (dist <= outer[mask])
        outside = np.all(bounds, axis=1)
        surface_points.extend(shell[outside])
    return np.array(surface_points)


def isiterable(obj):
    """
    Returns ``True`` if ``obj`` is iterable and not a string

    Adapted from MDAnalysis.lib.util.iterable
    """
    if isinstance(obj, str):
        return False
    if hasattr(obj, 'next'):
        return True
    if isinstance(obj, itertools.repeat):
        return True
    try:
        len(obj)
    except (TypeError, AttributeError):
        return False
    return True


def asiterable(obj):
    """
    Returns ``obj`` in a list if ``obj`` is not iterable
    """
    if not isiterable(obj):
        return [obj]
    return obj


def empty(obj):
    """Returns if ``obj`` is Falsy"""
    if isinstance(obj, np.ndarray):
        return True
    return not obj


def iter_single(obj, *args):
    """Return iterables of ``obj``, treating an empty list as an object"""
    if not isiterable(obj) or empty(obj) and not isinstance(obj, itertools.repeat):
        return itertools.repeat(obj, *args)
    return asiterable(obj)


def prepend_name_to_file(name, filename):
    head, tail = os.path.split(filename)
    if head and not head.endswith(r'/'):
        head += '/'
    return '{}{}_{}'.format(head, name, tail)