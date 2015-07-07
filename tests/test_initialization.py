import numpy
from numpy.testing import assert_raises, assert_allclose

import theano

from blocks.extras.initialization import PermutationMatrix
from blocks.extras.initialization import NormalizedInitialization


def test_permutation():
    def check_permutation(rng, shape):
        if shape[0] != shape[1]:
            assert_raises(ValueError, PermutationMatrix().generate, rng, shape)
            assert_raises(ValueError,
                          PermutationMatrix(
                              rng.permutation(shape[0])).generate,
                          rng, shape)
        else:
            W = PermutationMatrix().generate(rng, shape)
            assert_allclose([1.] * shape[0], W.sum(axis=0))
            assert_allclose([1.] * shape[0], W.sum(axis=1))

            W2 = PermutationMatrix().generate(rng, shape)
            assert_allclose([1.] * shape[0], W2.sum(axis=0))
            assert_allclose([1.] * shape[0], W2.sum(axis=1))
            assert (W != W2).any()

            perm = rng.permutation(shape[0])
            W = PermutationMatrix(perm).generate(rng, shape)
            assert_allclose([1.] * shape[0], W.sum(axis=0))
            assert_allclose([1.] * shape[0], W.sum(axis=1))
            assert_allclose(W, numpy.eye(shape[0])[:, perm])
            assert_raises(ValueError,
                          PermutationMatrix(perm).generate,
                          rng, (shape[0] + 1, shape[0] + 1))

    rng = numpy.random.RandomState(12345)
    yield check_permutation, rng, (5, 6)
    yield check_permutation, rng, (6, 7)
    yield check_permutation, rng, (5, 5)
    yield check_permutation, rng, (3, 3)
    yield check_permutation, rng, (8, 8)
    yield check_permutation, rng, (200, 200)


def test_normalized():
    rng = numpy.random.RandomState(1)

    def check_normalized(rng, shape):
        weights = NormalizedInitialization().generate(rng, shape)
        assert weights.shape == shape
        assert weights.dtype == theano.config.floatX
        assert_allclose(weights.mean(), 0, atol=1e-2)
        std = 2 * numpy.sqrt(6. / (shape[0] + shape[1])) / numpy.sqrt(12)
        assert_allclose(weights.std(), std, atol=1e-2)
    yield check_normalized, rng, (500, 600)
    yield check_normalized, rng, (600, 500)
