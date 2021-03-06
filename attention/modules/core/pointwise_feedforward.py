import sonnet as snt
import tensorflow as tf


class PointWiseFeedForward(snt.AbstractModule):
    def __init__(self,
                 hidden_size,
                 output_size,
                 dropout_rate=0.0):
        super(PointWiseFeedForward, self).__init__(name="pointwise_feedforward")
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.dropout_rate = dropout_rate

    def _build(self, inputs):
        """

        :param inputs:
        :return:
        """
        hidden_size, output_size = self.hidden_size, self.output_size

        def pointwise(x):
            hidden = snt.Conv1D(output_channels=output_size, kernel_shape=1)(x)
            if self.dropout_rate > 0.0:
                hidden = tf.layers.dropout(hidden, self.dropout_rate)
            hidden = tf.nn.relu(hidden)

            outputs = snt.Conv1D(output_channels=output_size, kernel_shape=1)(hidden)
            if self.dropout_rate > 0.0:
                outputs = tf.layers.dropout(outputs, self.dropout_rate)
            return tf.nn.relu(outputs)

        return pointwise(inputs)
