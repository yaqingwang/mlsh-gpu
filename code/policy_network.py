import rl_algs.common.tf_util as U
import tensorflow as tf
import numpy as np
import gym
from rl_algs.common.distributions import CategoricalPdType
from running_mean_std import RunningMeanStd
from subpolicy_network import feature_net
import pdb


class Policy(object):
    def _mlp(self, obs, num_subpolicies, hid_size, num_hid_layers, ac_space, 
            gaussian_fixed_var):
        # value function
        last_out = obs
        for i in range(num_hid_layers):
            last_out = tf.nn.tanh(U.dense(last_out, hid_size, "vffc%i"%(i+1), 
                weight_init=U.normc_initializer(1.0)))
        self.vpred = U.dense(last_out, 1, "vffinal", weight_init=U.normc_initializer(1.0))[:,0]

        # master policy
        last_out = obs
        for i in range(num_hid_layers):
            last_out = tf.nn.tanh(U.dense(last_out, hid_size, "masterpol%i"%(i+1), 
                weight_init=U.normc_initializer(1.0)))
        self.selector = U.dense(last_out, num_subpolicies, "masterpol_final", 
                U.normc_initializer(0.01))
        self.pdtype = pdtype = CategoricalPdType(num_subpolicies)
        self.pd = pdtype.pdfromflat(self.selector)

    def _cnn(self, obs, num_subpolicies):
        features = feature_net(obs)
        self.vpred = U.dense(features, 1, "vffinal", weight_init=U.normc_initializer(1.0))[:,0]
        self.selector = U.dense(features, num_subpolicies, "masterpol_final", 
                U.normc_initializer(0.01))
        self.pdtype = pdtype = CategoricalPdType(num_subpolicies)
        self.pd = pdtype.pdfromflat(self.selector)

    def __init__(self, name, ob, ac_space, num_subpolicies, network='mlp', 
            gaussian_fixed_var=True):
        self.num_subpolicies = num_subpolicies
        self.gaussian_fixed_var = gaussian_fixed_var
        shape = []
        for d in range(1, len(ob.shape)):
            shape.append(ob.shape[d])

        with tf.variable_scope("obfilter", reuse=tf.AUTO_REUSE):
            self.ob_rms = RunningMeanStd(shape=shape)
        obs = tf.clip_by_value((ob - self.ob_rms.mean) / self.ob_rms.std, -5.0, 5.0)

        with tf.variable_scope(name):
            self.scope = tf.get_variable_scope().name

            if network == 'mlp':
                hid_size=64 
                num_hid_layers=2
                self.hid_size = hid_size
                self.num_hid_layers = num_hid_layers
                self._mlp(obs, num_subpolicies, hid_size, num_hid_layers, ac_space, 
                        gaussian_fixed_var)
            elif network == 'cnn':
                self._cnn(obs, num_subpolicies)


        # sample actions
        stochastic = tf.placeholder(dtype=tf.bool, shape=())
        ac = U.switch(stochastic, self.pd.sample(), self.pd.mode())
        self._act = U.function([stochastic, ob], [ac, self.vpred])

        # debug
        self._debug = U.function([stochastic, ob], [ac, self.selector])
        self._act_forced = U.function([stochastic, ob, self.selector], [ac, self.vpred])

    def act(self, stochastic, ob):
        ac1, vpred1 =  self._act(stochastic, ob)#ob[None])
        return ac1, vpred1#ac1[0], vpred1[0]
    def get_variables(self):
        return tf.get_collection(tf.GraphKeys.VARIABLES, self.scope)
    def get_trainable_variables(self):
        return tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, self.scope)
    def reset(self):
        with tf.variable_scope(self.scope, reuse=True):
            varlist = self.get_trainable_variables()
            initializer = tf.variables_initializer(varlist)
            U.get_session().run(initializer)

    # debug
    def act_forced(self, stochastic, ob, policy):
        softmax = np.zeros(self.num_subpolicies)
        softmax[policy] = 1
        ac1, vpred1 =  self._act_forced(stochastic, ob[None], softmax)
        return ac1[0], vpred1[0]
    def debug(self, stochastic, ob):
        _, sel = self._debug(stochastic, ob[None])
        return sel[0]
