from collections import defaultdict
from itertools import combinations

import numpy as np
from pymatgen import PeriodicSite
from pymatgen.analysis.graphs import StructureGraph

from crystal_toolkit.core.scene import Scene


def _get_sites_to_draw(
    self, draw_image_atoms=True, bonded_sites_outside_unit_cell=False
):
    """
    Returns a list of site indices and image vectors.
    """

    sites_to_draw = [(idx, (0, 0, 0)) for idx in range(len(self.structure))]

    if draw_image_atoms:

        for idx, site in enumerate(self.structure):

            zero_elements = [
                idx
                for idx, f in enumerate(site.frac_coords)
                if np.allclose(f, 0, atol=0.05)
            ]

            coord_permutations = [
                x
                for l in range(1, len(zero_elements) + 1)
                for x in combinations(zero_elements, l)
            ]

            for perm in coord_permutations:
                sites_to_draw.append(
                    (idx, (int(0 in perm), int(1 in perm), int(2 in perm)))
                )

            one_elements = [
                idx
                for idx, f in enumerate(site.frac_coords)
                if np.allclose(f, 1, atol=0.05)
            ]

            coord_permutations = [
                x
                for l in range(1, len(one_elements) + 1)
                for x in combinations(one_elements, l)
            ]

            for perm in coord_permutations:
                sites_to_draw.append(
                    (idx, (-int(0 in perm), -int(1 in perm), -int(2 in perm)))
                )

    if bonded_sites_outside_unit_cell:

        sites_to_append = []
        for (n, jimage) in sites_to_draw:
            connected_sites = self.get_connected_sites(n, jimage=jimage)
            for connected_site in connected_sites:
                if connected_site.jimage != (0, 0, 0):
                    sites_to_append.append(
                        (connected_site.index, connected_site.jimage)
                    )
        sites_to_draw += sites_to_append

    # remove any duplicate sites
    # (can happen when enabling bonded_sites_outside_unit_cell,
    #  since this works by following bonds, and a single site outside the
    #  unit cell can be bonded to multiple atoms within it)
    return set(sites_to_draw)


def get_structure_graph_scene(
    self,
    origin=(0, 0, 0),
    draw_image_atoms=True,
    bonded_sites_outside_unit_cell=True,
    hide_incomplete_bonds=False,
    explicitly_calculate_polyhedra_hull=False,
) -> Scene:

    primitives = defaultdict(list)

    sites_to_draw = self._get_sites_to_draw(
        draw_image_atoms=draw_image_atoms,
        bonded_sites_outside_unit_cell=bonded_sites_outside_unit_cell,
    )

    for (idx, jimage) in sites_to_draw:

        site = self.structure[idx]
        if jimage != (0, 0, 0):
            connected_sites = self.get_connected_sites(idx, jimage=jimage)
            site = PeriodicSite(
                site.species,
                np.add(site.frac_coords, jimage),
                site.lattice,
                properties=site.properties,
            )
        else:
            connected_sites = self.get_connected_sites(idx)

        true_number_of_connected_sites = len(connected_sites)
        connected_sites_being_drawn = [
            cs for cs in connected_sites if (cs.index, cs.jimage) in sites_to_draw
        ]
        number_of_connected_sites_drawn = len(connected_sites_being_drawn)
        all_connected_sites_present = (
            true_number_of_connected_sites == number_of_connected_sites_drawn
        )
        if hide_incomplete_bonds:
            # only draw bonds if the destination site is also being drawn
            connected_sites = connected_sites_being_drawn

        site_scene = site.get_scene(
            connected_sites=connected_sites,
            all_connected_sites_present=all_connected_sites_present,
            origin=origin,
            explicitly_calculate_polyhedra_hull=explicitly_calculate_polyhedra_hull,
        )
        for scene in site_scene.contents:
            primitives[scene.name] += scene.contents

    # we are here ...
    # select polyhedra
    # split by atom type at center
    # see if any intersect, if yes split further
    # order sets, with each choice, go to add second set etc if don't intersect
    # they intersect if centre atom forms vertex of another atom (caveat: centre atom may not actually be inside polyhedra! not checking for this, add todo)
    # def _set_intersects() ->bool:
    # def _split_set() ->List: (by type, then..?)
    # def _order_sets()... pick 1, ask can add 2? etc

    primitives["unit_cell"].append(self.structure.lattice.get_scene(origin=origin))

    return Scene(
        name=self.structure.composition.reduced_formula,
        contents=[Scene(name=k, contents=v) for k, v in primitives.items()],
    )


StructureGraph._get_sites_to_draw = _get_sites_to_draw
StructureGraph.get_scene = get_structure_graph_scene
