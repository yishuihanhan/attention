import tensorflow as tf
import sonnet as snt


class MultiHeadAttention(snt.AbstractModule):
    def __init__(self, num_heads, dropout_rate=0.0, mask_leftward_decoder=False):
        super(MultiHeadAttention, self).__init__(name="multihead_attention")

        self.num_heads = num_heads
        self.dropout_rate = dropout_rate
        self.mask_leftward_decoder = mask_leftward_decoder

    def create_mask_for_keys(self, keys, keys_length):
        # batch_size x keys_l
        mask = 1 - tf.sequence_mask(lengths=keys_length, maxlen=keys.get_shape().as_list()[1], dtype=tf.float32)
        mask *= -2 ** 30
        mask = tf.expand_dims(tf.expand_dims(mask, 1), 1)  # batch_size x 1 x 1 x keys_l
        return mask

    def create_mask_for_queries(self, queries, queries_len):
        # batch_size x queries_l
        mask = tf.sequence_mask(lengths=queries_len, maxlen=queries.get_shape().as_list()[1], dtype=tf.float32)
        mask = tf.expand_dims(tf.expand_dims(mask, 1), -1)  # batch_size x 1 x queries x 1
        return mask

    def create_mask_for_decoding(self, queries_len, keys_len):
        masking_leftward = 1 - tf.contrib.linalg.LinearOperatorTriL(tf.ones((queries_len, keys_len))).to_dense()
        masking_leftward = tf.expand_dims(tf.expand_dims(masking_leftward, 0), 0)
        masking_leftward *= - 2 ** 30
        return masking_leftward

    def _build(self, queries, keys, queries_len, keys_len, values=None):
        if values is None:
            values = keys
        input_dim = queries.get_shape().as_list()[-1]

        q_w = tf.contrib.layers.fully_connected(queries, input_dim)  # batch_size x query_l x d_model
        k_w = tf.contrib.layers.fully_connected(keys, input_dim)  # batch_size x keys_l x d_model
        v_w = tf.contrib.layers.fully_connected(values, input_dim)  # batch_size x values_l x d_model

        # batch_size x num_head x [queries|keys|values]_l x d_model / 8
        q_wi = tf.transpose(tf.split(q_w, self.num_heads, axis=2), [1, 0, 2, 3])
        k_wi = tf.transpose(tf.split(k_w, self.num_heads, axis=2), [1, 0, 2, 3])
        v_wi = tf.transpose(tf.split(v_w, self.num_heads, axis=2), [1, 0, 2, 3])

        def dot_product_att(query, key):
            head_i = tf.matmul(query, tf.transpose(key, [0, 2, 1])) / key.get_shape().as_list()[-1] ** 0.5
            return head_i

        dot_prod_op = snt.BatchApply(dot_product_att)
        logits_q_wi_k_wi = dot_prod_op(q_wi, k_wi)  # batch_size x num_heads x query_l x key_l

        mask_keys = self.create_mask_for_keys(keys, keys_len)  # batch_size x num_heads x 1 x keys_l
        logits_q_wi_k_wi += mask_keys  # batch_size x num_heads x queries_l x keys_l

        if self.mask_leftward_decoder:
            logits_q_wi_k_wi += self.create_mask_for_decoding(*logits_q_wi_k_wi.get_shape().as_list()[2:])

        softmax_q_wi_k_wi = tf.nn.softmax(logits_q_wi_k_wi)  # batch_size x num_heads x queries_l x keys_l

        mask_queries = self.create_mask_for_queries(queries, queries_len)  # batch_size x num_heads x queries_l x 1
        softmax_q_wi_k_wi *= mask_queries  # batch_size x num_heads x queries_l x keys_l

        if self.dropout_rate > 0.0:
            softmax_q_wi_k_wi = tf.layers.dropout(softmax_q_wi_k_wi, self.dropout_rate)

        attention_qwi_kwi = tf.matmul(softmax_q_wi_k_wi, v_wi)  # batch_size x num_heads x queries_l x d_model / 8
        # batch_size x queries_l x d_model / 8 x num_heads
        attention_qwi_kwi = tf.transpose(attention_qwi_kwi, [0, 2, 3, 1])

        # batch_size x queries_l x input_len
        concat_attention = tf.reshape(attention_qwi_kwi, [-1, queries.get_shape().as_list()[1], input_dim])

        multi_attention = tf.contrib.layers.fully_connected(concat_attention, input_dim)
        return multi_attention
