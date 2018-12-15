#!/usr/bin/env python
# coding: utf-8
"""
Tests for the computation of the Green function and the resolution of the BEM problem.
"""

import pytest

import numpy as np

from capytaine.mesh.mesh import Mesh
from capytaine.mesh.meshes_collection import CollectionOfMeshes
from capytaine.mesh.symmetries import AxialSymmetry, ReflectionSymmetry, TranslationalSymmetry

from capytaine.bodies import FloatingBody
from capytaine.geometric_bodies.sphere import Sphere
from capytaine.geometric_bodies.cylinder import Disk, HorizontalCylinder

from capytaine.problems import RadiationProblem
from capytaine.Nemoh import Nemoh

from capytaine.tools.geometry import xOz_Plane, yOz_Plane

from capytaine.matrices.low_rank_blocks import LowRankMatrix

solver = Nemoh(use_symmetries=True, matrix_cache_size=0)


@pytest.mark.parametrize("reso", range(1, 3))
@pytest.mark.parametrize("depth", [10.0, np.infty])
def test_floating_sphere(reso, depth):
    full_sphere = Sphere(radius=1.0, ntheta=reso, nphi=4*reso, clever=False, clip_free_surface=True)
    full_sphere.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=full_sphere, omega=1.0, sea_bottom=-depth)
    result1 = solver.solve(problem)

    half_sphere_mesh = full_sphere.mesh.extract_faces(np.where(full_sphere.mesh.faces_centers[:, 1] > 0)[0])
    two_halves_sphere = FloatingBody(ReflectionSymmetry(half_sphere_mesh, xOz_Plane))
    two_halves_sphere.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=two_halves_sphere, omega=1.0, sea_bottom=-depth)
    result2 = solver.solve(problem)

    quarter_sphere = half_sphere_mesh.extract_faces(np.where(half_sphere_mesh.faces_centers[:, 0] > 0)[0])
    quarter_sphere.name = "quarter_sphere"
    four_quarter_sphere = FloatingBody(ReflectionSymmetry(ReflectionSymmetry(quarter_sphere, yOz_Plane), xOz_Plane))
    assert 'None' not in four_quarter_sphere.mesh.tree_view()
    four_quarter_sphere.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=four_quarter_sphere, omega=1.0, sea_bottom=-depth)
    result3 = solver.solve(problem)

    clever_sphere = Sphere(radius=1.0, ntheta=reso, nphi=4*reso, clever=True, clip_free_surface=True)
    clever_sphere.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=clever_sphere, omega=1.0, sea_bottom=-depth)
    result4 = solver.solve(problem)

    # (quarter_sphere + half_sphere + full_sphere + clever_sphere).show()

    volume = 4/3*np.pi
    assert np.isclose(result1.added_masses["Heave"], result2.added_masses["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.added_masses["Heave"], result3.added_masses["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.added_masses["Heave"], result4.added_masses["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.radiation_dampings["Heave"], result2.radiation_dampings["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.radiation_dampings["Heave"], result3.radiation_dampings["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.radiation_dampings["Heave"], result4.radiation_dampings["Heave"], atol=1e-4*volume*problem.rho)


def test_join_axisymmetric_disks():
    disk1 = Disk(radius=1.0, center=(-1, 0, 0), resolution=(6, 6), axial_symmetry=True).mesh
    disk2 = Disk(radius=2.0, center=(1, 0, 0), resolution=(8, 6), axial_symmetry=True).mesh
    joined = disk1.join_meshes(disk2, name="two_disks")
    assert isinstance(joined, AxialSymmetry)
    joined.tree_view()

    disk3 = Disk(radius=1.0, center=(0, 0, 0), resolution=(6, 4), axial_symmetry=True).mesh
    with pytest.raises(AssertionError):
        disk1.join_meshes(disk3)


def test_join_translational_cylinders():
    mesh1 = HorizontalCylinder(length=10.0, radius=1.0, center=(0, 5, -5), clever=True, nr=0, ntheta=10, nx=10).mesh
    mesh2 = HorizontalCylinder(length=10.0, radius=2.0, center=(0, -5, -5), clever=True, nr=0, ntheta=10, nx=10).mesh
    joined = mesh1.join_meshes(mesh2)
    assert isinstance(joined, TranslationalSymmetry)


def test_odd_axial_symmetry():
    """Buoy with odd number of slices."""
    def shape(z):
            return 0.1*(-(z+1)**2 + 16)
    buoy = FloatingBody(AxialSymmetry.from_profile(shape, z_range=np.linspace(-5.0, 0.0, 9), nphi=5))
    buoy.add_translation_dof(direction=(0, 0, 1), name="Heave")

    problem = RadiationProblem(body=buoy, omega=2.0)
    result1 = solver.solve(problem)

    full_buoy = FloatingBody(buoy.mesh.merge())
    full_buoy.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=full_buoy, omega=2.0)
    result2 = solver.solve(problem)

    volume = buoy.mesh.volume
    assert np.isclose(result1.added_masses["Heave"], result2.added_masses["Heave"], atol=1e-4*volume*problem.rho)
    assert np.isclose(result1.radiation_dampings["Heave"], result2.radiation_dampings["Heave"], atol=1e-4*volume*problem.rho)


@pytest.mark.parametrize("depth", [10.0, np.infty])
def test_horizontal_cylinder(depth):
    cylinder = HorizontalCylinder(length=10.0, radius=1.0, clever=False, nr=2, ntheta=10, nx=10)
    assert isinstance(cylinder.mesh, Mesh)
    cylinder.translate_z(-3.0)
    cylinder.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=cylinder, omega=1.0, sea_bottom=-depth)
    result1 = solver.solve(problem)

    sym_cylinder = HorizontalCylinder(length=10.0, radius=1.0, clever=True, nr=2, ntheta=10, nx=10)
    assert isinstance(sym_cylinder.mesh, CollectionOfMeshes)
    assert isinstance(sym_cylinder.mesh[0], TranslationalSymmetry)
    sym_cylinder.translate_z(-3.0)
    sym_cylinder.add_translation_dof(direction=(0, 0, 1), name="Heave")
    problem = RadiationProblem(body=sym_cylinder, omega=1.0, sea_bottom=-depth)
    result2 = solver.solve(problem)

    assert np.isclose(result1.added_masses["Heave"], result2.added_masses["Heave"], atol=1e-4*cylinder.volume*problem.rho)
    assert np.isclose(result1.radiation_dampings["Heave"], result2.radiation_dampings["Heave"], atol=1e-4*cylinder.volume*problem.rho)


def test_array_of_spheres():
    radius = 1.0
    resolution = 2
    perimeter = 2*np.pi*radius
    buoy = Sphere(radius=radius, center=(0.0, 0.0, 0.0),
                  ntheta=int(perimeter*resolution/2), nphi=int(perimeter*resolution),
                  clip_free_surface=True, clever=True, name=f"buoy")
    buoy.add_translation_dof(name="Surge")
    buoy.add_translation_dof(name="Sway")
    buoy.add_translation_dof(name="Heave")

    # Corner case
    dumb_array = buoy.assemble_regular_array(distance=5.0, nb_bodies=(1, 1))
    assert dumb_array.mesh == buoy.mesh

    # Main case
    array = buoy.assemble_regular_array(distance=5.0, nb_bodies=(3, 3))

    assert isinstance(array.mesh, TranslationalSymmetry)
    assert isinstance(array.mesh[0], TranslationalSymmetry)
    assert array.mesh[0][0] == buoy.mesh

    assert len(array.dofs) == 3*3*3
    assert "2_0_Heave" in array.dofs


def test_low_rank_matrices():
    radius = 1.0
    resolution = 2
    perimeter = 2*np.pi*radius
    buoy = Sphere(radius=radius, center=(0.0, 0.0, 0.0),
                  ntheta=int(perimeter*resolution/2), nphi=int(perimeter*resolution),
                  clip_free_surface=True, clever=False, name=f"buoy")
    buoy.add_translation_dof(name="Heave")
    full_farm = FloatingBody.join_bodies(buoy, buoy.translated_x(10))
    full_farm.mesh._meshes[1].name = "other_buoy_mesh"

    S, V = solver.build_matrices(full_farm.mesh, full_farm.mesh)
    assert isinstance(S.all_blocks[0, 1], LowRankMatrix)
    assert isinstance(S.all_blocks[1, 0], LowRankMatrix)
    print(S.all_blocks[1, 0].rank)

    problem = RadiationProblem(body=full_farm, omega=1.0, radiating_dof="buoy__Heave")
    result = Nemoh(linear_solver="gmres").solve(problem)
    result2 = Nemoh(linear_solver="gmres", use_symmetries=False).solve(problem)

    assert np.isclose(result.added_masses['buoy__Heave'], result2.added_masses['buoy__Heave'], atol=10.0)
    assert np.isclose(result.radiation_dampings['buoy__Heave'], result2.radiation_dampings['buoy__Heave'], atol=10.0)

