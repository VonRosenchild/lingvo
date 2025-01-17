# Lint as: python2, python3
# Copyright 2019 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Input extractors.

Input extractors are an API for parsing and processing a set of fields from
serialized records.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from lingvo import compat as tf
from lingvo.core import base_layer
from lingvo.core import py_utils

from lingvo.tasks.car import base_extractor

BaseExtractor = base_extractor._BaseExtractor  # pylint:disable=protected-access
BUCKET_UPPER_BOUND = base_extractor.BUCKET_UPPER_BOUND


################################################################################
# Extractors for car data.
################################################################################
class FieldsExtractor(base_layer.BaseLayer):
  """An API for parsing and processing a set of fields from serialized records.

  Input generators often need to parse several fields from a serialized record.
  This involves two stages: specifying the name and type of the fields to
  extract from serialized records (tf.Example or tf.SequenceExample), and then
  processing the raw output into a form to be consumed by higher-level callers.

  This class attempts to modularize this processing within the Minecraft input
  generators, so that users can easily create input generator pipelines that mix
  and match the composition of different fields from the same dataset.

  A descendant of this class will implement three functions:

    1) FeatureMap(): returning a dictionary of field names to field types, e.g.,
       'images' to tf.VarLenFeature(tf.string).  For PlainTextIterator
       datasets, FeatureMap() should be empty.

    2) _Extract(features): Given a 'features' dictionary containing the result
       from calling tf.parse_example or tf.parse_sequence_example on all
       extractors' features, produce a NestedMap of Tensors.

       NOTE: The return of the overall pipeline is a NestedMap of batched
       Tensors. However, the names and associations of the fields of each
       extractor are lost on the boundary of the map fn.  At the moment, one
       must implement _Extract() such that the names of the fields returned in
       the NestedMap matches self.Shape()'s keys; this is checked during the
       parent's Extract() call.

    3) Shape(): A NestedMap mapping names of outputs to their static shape,
       without the batch dimension.  In InputBatch, this shape will be used to
       ensure that every output has a statically known shape.

  The caller of Extractors calls each extractor's FeatureMap() to populate the
  schema passed to tf.parse_example() or tf.parse_sequence_example(). The
  resulting dicationary of Tensors is then passed to each extractor's _Extract()
  function (via FieldsExtractor.Extract()) to return each extractor's output.

  It is the responsibility of the caller to maintain orders of outputs, since
  NestedMaps do not have any inherent ordering during iteration.
  """

  @classmethod
  def Params(cls):
    """Defaults params."""
    p = super(FieldsExtractor, cls).Params()
    p.name = cls.__name__
    return p

  def FeatureMap(self):
    """Return an dictionary from tf.Example feature names to Features."""
    raise NotImplementedError()

  def Extract(self, features):
    """Given 'feature' (Sparse)Tensors, output Tensors for consumption.

    NOTE: Implementation provided by subclasses's _Extract() method.

    Args:
      features: A dictionary of (Sparse)Tensors which includes tensors from all
        extractors.

    Returns:
      A NestedMap of output Tensors.
    """
    outputs = self._Extract(features)
    shapes = self.Shape()
    assert outputs.IsCompatible(shapes), '{} vs. {}'.format(
        outputs.DebugString(), shapes.DebugString())
    return outputs

  def Filter(self, outputs):
    """Return the bucket based on the result of Extract().

    This function should return 1 if the example should pass through without
    being dropped, and BUCKET_UPPER_BOUND if the example should be dropped.

    Args:
      outputs: The NestedMap returned by this extractor's _Extract() function.
        This is useful to implement filtering based on the values of the
        extracted example.

    Returns:
      A scalar bucket id.
    """
    del outputs
    return 1

  def Shape(self):
    """Return a NestedMap of un-batched fully-specified tf.TensorShapes."""
    raise NotImplementedError()

  def DType(self):
    """Return a NestedMap mapping names to tf.DType."""
    raise NotImplementedError()

  def _Extract(self, features):
    """The subclass-defined implementation of Extract().

    Args:
      features: A dictionary of (Sparse)Tensors which includes tensors from all
        extractors.

    Returns:
      A NestedMap of output Tensors whose key names match self.Shape()'s keys.
    """
    raise NotImplementedError()


class LaserExtractor(FieldsExtractor):
  """Interface for extracting laser data.

  Must produce:
    points_xyz: [max_num_points, 3] - XYZ coordinates of laser points.

    points_feature: [max_num_points, num_features] - Features for each point in
      points_xyz.

    points_padding: [max_num_points]: Padding for points.  0 means the
      corresponding point is the original, and 1 means there is no point
      (xyz or feature) present.  Only present if max_num_points is not
      None.

  """

  @classmethod
  def Params(cls):
    p = super(LaserExtractor, cls).Params()
    p.Define('max_num_points', None, 'The number of points per spin.')
    p.Define('num_features', 1, 'Number of features per laser point.')
    return p

  def Shape(self):
    p = self.params
    ret = py_utils.NestedMap(
        points_xyz=tf.TensorShape([p.max_num_points, 3]),
        points_feature=tf.TensorShape([p.max_num_points, p.num_features]))
    if p.max_num_points is not None:
      ret.points_padding = tf.TensorShape([p.max_num_points])
    return ret

  def DType(self):
    ret = py_utils.NestedMap(points_xyz=tf.float32, points_feature=tf.float32)
    if self.params.max_num_points is not None:
      ret.points_padding = tf.float32
    return ret
