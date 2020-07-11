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

import logging
import time

import numpy as np
import scipy as sp
from scipy.sparse.linalg import lsqr
from tqdm.auto import trange

from .utilities import (meanCurvatureLaplaceWeights, getMeshVPos,
                        averageFaceArea, getOneRingAreas, make_trimesh)

logger = logging.getLogger('skeletor')

if not logger.handlers:
    logger.addHandler(logging.StreamHandler())


def contract(mesh, iterations=10, SL=10, WC=2, lsqr_tol=1e-07, progress=True):
    """Contract mesh.

    Parameters
    ----------
    mesh :          mesh obj
                    The mesh to be contracted. Can any object (e.g.
                    a trimesh.Trimesh) that has ``.vertices`` and ``.faces``
                    properties or a tuple ``(vertices, faces)`` or a dictionary
                    ``{'vertices': vertices, 'faces': faces}``.
                    Vertices and faces must be (N, 3) numpy arrays.
    iterations :    int, optional
                    Max rounds of contractions. Note that the algorithm might
                    stop early if the sum of the face areas increases from one
                    iteration to the next instead of decreasing.
    SL :            float, optional
                    Factor by which the contraction matrix is multiplied for
                    each iteration. Lower values are more likely to get you
                    an optimal contraction at the cost of needing more
                    iterations.
    WC :            float, optional
                    Weight factor that affects the attraction constraint.
    lsqr_tol :      float, optional
                    Sets the stopping tolerances for finding the least-squares
                    solution (`atol` and `btol` in `scipy.sparse.linalg.lsqr`).
                    Increasing the tolerance will give dramatic speed-ups but
                    may lead to funny contractions.

    Returns
    -------
    trimesh.Trimesh
                    Contracted copy of original mesh.

    """
    # Force into trimesh
    m = make_trimesh(mesh)

    n = len(m.vertices)
    #initialFaceWeight = (10**-3) * np.sqrt(averageFaceArea(m))
    initialFaceWeight = 1.0 / (10.0 * np.sqrt(averageFaceArea(m)))
    originalOneRing = getOneRingAreas(m)
    zeros = np.zeros((n, 3))

    full_start = time.time()

    WH0_diag = np.zeros(n)
    WH0_diag.fill(WC)
    WH0 = sp.sparse.spdiags(WH0_diag, 0, WH0_diag.size, WH0_diag.size)

    # Make a copy but keep original values
    WH = sp.sparse.dia_matrix(WH0)

    WL_diag = np.zeros(n)
    WL_diag.fill(initialFaceWeight)
    WL = sp.sparse.spdiags(WL_diag, 0, WL_diag.size, WL_diag.size)

    # Copy mesh
    dm = m.copy()

    L = -meanCurvatureLaplaceWeights(dm, normalized=True)

    area_ratios = []
    area_ratios.append(1.0)
    originalFaceAreaSum = np.sum(originalOneRing)
    goodvertices = [[]]
    timetracker = []

    for i in trange(iterations, desc='Contracting', disable=progress is False):
        start = time.time()
        vpos = getMeshVPos(dm)
        A = sp.sparse.vstack([L.dot(WL), WH])
        b = np.vstack((zeros, WH.dot(vpos)))
        cpts = np.zeros((n, 3))

        for j in range(3):
            cpts[:, j] = lsqr(A, b[:, j], atol=lsqr_tol, btol=lsqr_tol)[0]

        dm.vertices = cpts

        end = time.time()
        logger.debug('TOTAL TIME FOR SOLVING LEAST SQUARES: {:.3f}s'.format(end - start))
        newringareas = getOneRingAreas(dm)
        changeinarea = np.power(newringareas, -0.5)
        area_ratios.append(np.sum(newringareas) / originalFaceAreaSum)

        if(area_ratios[-1] > area_ratios[-2]):
            logger.debug('FACE AREA INCREASED FROM PREVIOUS: {:.4f} {:.4f}'.format(area_ratios[-1], area_ratios[-2]))
            logger.debug('ITERATION TERMINATED AT: {}'.format(i))
            logger.debug('RESTORE TO PREVIOUS GOOD POSITIONS FROM ITERATION: {}'.format(i - 1))

            cpts = goodvertices[0]
            dm.vertices = cpts
            break

        goodvertices[0] = cpts
        logger.debug('RATIO OF CHANGE IN FACE AREA: {:.4f}'.format(area_ratios[-1]))
        WL = sp.sparse.dia_matrix(WL.multiply(SL))
        WH = sp.sparse.dia_matrix(WH0.multiply(changeinarea))
        L = -meanCurvatureLaplaceWeights(dm, normalized=True)
        full_end = time.time()

        timetracker.append(full_end - full_start)
        full_start = time.time()

    logger.debug('TOTAL TIME FOR MESH CONTRACTION ::: {:.2f}s FOR VERTEX COUNT ::: #{}'.format(np.sum(timetracker), n))
    return dm