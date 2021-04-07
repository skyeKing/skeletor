#    This script is part of skeletor (http://www.github.com/schlegelp/skeletor).
#    Copyright (C) 2018 Philipp Schlegel
#    Modified from https://github.com/aalavandhaann/Py_BL_MeshSkeletonization
#    by #0K Srinivasan Ramachandran.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.

import numpy as np
import trimesh as tm

from .utils import reindex_swc

__docformat__ = "numpy"


class Skeleton:
    """Class representing a skeleton.

    Typically used to hold results from the skeletonization.

    Attributes
    ----------
    swc :       pd.DataFrame, optional
                SWC table.
    vertices :  (N, 3) array
                Vertex (node) positions.
    edges :     (M, 2) array
                Indices of connected vertex pairs.
    radii :    (N, ) array, optional
                Radii for each vertex (node) in the skeleton.
    mesh :      Trimesh, optional
                The original mesh.
    mesh_map :  array, optional
                Same length as ``mesh``. Maps mesh vertices to vertices (nodes)
                in the skeleton.
    method :    str, optional
                Which method was used to generate the skeleton.

    """

    def __init__(self, swc, mesh=None, mesh_map=None, method=None):
        self.swc = swc
        self.mesh = mesh
        self.mesh_map = mesh_map
        self.method = method

    def __str__(self):
        """Summary."""
        return self.__repr__()

    def __repr__(self):
        """Return quick summary of the skeleton's geometry."""
        elements = []
        if hasattr(self, 'vertices'):
            elements.append(f'vertices={self.vertices.shape}')
        if hasattr(self, 'edges'):
            elements.append(f'edges={self.edges.shape}')
        if hasattr(self, 'method'):
            elements.append(f'method={self.method}')
        return f'<Skeleton({", ".join(elements)})>'

    @property
    def edges(self):
        """Return skeleton edges."""
        return self.swc.loc[self.swc.parent_id >= 0,
                            ['node_id', 'parent_id']].values

    @property
    def vertices(self):
        """Return skeleton vertices (nodes)."""
        return self.swc[['x', 'y', 'z']].values

    @property
    def radius(self):
        """Return radii."""
        if 'radius' not in self.swc.columns:
            raise ValueError('No radius info found. Run `skeletor.post.radii()`'
                             ' to get them.')
        return self.swc['radius'].values,

    @property
    def skeleton(self):
        """Skeleton as trimesh Path3D."""
        if not hasattr(self, '_skeleton'):
            lines = [tm.path.entities.Line(e) for e in self.edges]

            self._skeleton = tm.path.Path3D(entities=lines,
                                            vertices=self.vertices,
                                            process=False)
        return self._skeleton

    def reindex(self, inplace=False):
        """Clean up skeleton."""
        x = self
        if not inplace:
            x = x.copy()

        # Re-index to make node IDs continous again
        x.swc, new_ids = reindex_swc(x.swc)

        # Update mesh map
        if not isinstance(x.mesh_map, type(None)):
            x.mesh_map = np.array([new_ids.get(i, i) for i in x.mesh_map])

        if not inplace:
            return x

    def copy(self):
        """Return copy of the skeleton."""
        return Skeleton(swc=self.swc.copy() if not isinstance(self.swc, type(None)) else None,
                        mesh=self.mesh.copy() if not isinstance(self.mesh, type(None)) else None,
                        mesh_map=self.mesh_map.copy() if not isinstance(self.mesh_map, type(None)) else None)

    def scene(self, mesh=False, **kwargs):
        """Return a Scene object containing the skeleton.

        Returns
        -------
        scene :     trimesh.scene.scene.Scene
                    Contains the skeleton and optionally the mesh.

        """
        if mesh:
            if isinstance(self.mesh, type(None)):
                raise ValueError('Skeleton has no mesh.')

            self.mesh.visual.face_colors = [100, 100, 100, 100]

            # Note the copy(): without it the transform in show() changes
            # the original meshes
            sc = tm.Scene([self.mesh.copy(), self.skeleton.copy()], **kwargs)
        else:
            sc = tm.Scene(self.skeleton, **kwargs)

        return sc

    def show(self, mesh=False, **kwargs):
        """Render the skeleton in an opengl window. Requires pyglet.

        Parameters
        ----------
        mesh :      bool
                    If True, will render transparent mesh on top of the
                    skeleton.

        Returns
        --------
        scene :     trimesh.scene.Scene
                    Scene with skeleton in it.

        """
        scene = self.scene(mesh=mesh)

        # I encountered some issues if object space is big and the easiest
        # way to work around this is to apply a transform such that the
        # coordinates have -5 to +5 bounds
        fac = 5 / self.skeleton.bounds[1].max()
        scene.apply_transform(np.diag([fac, fac, fac, 1]))

        return scene.show(**kwargs)