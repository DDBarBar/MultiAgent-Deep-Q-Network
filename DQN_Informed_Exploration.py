import numpy as np
import random
from collections import deque
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.optimizers import Adam
from DQN_Agent import DQN_Agent

class DQN_Informed_Exploration(DQN_Agent):
    def __init__(self, env):
        self.env = env
        self.replay_memory = deque(maxlen=200000)

        self.gamma = 0.99
        self.epsilon = 1.0
        self.epsilon_min = 0.01
        self.epsilon_decay = 0.9995
        self.learning_rate = 0.05
        self.target_update_counter = 0
        self.C = 8 # intervcal for updating target network
        self.initial_random_steps = 100000
        self.actions_count = 0
        self.clip_errors = True

        self.q_network = self.init_q_network()
        self.target_q_network = self.init_q_network()
        self.dynamics_model = self.init_dynamics_model()
        self.update_count = 0
        self.dynamics_model_converged = False

    def update_model(self, state, action, reward, new_state, done):

        self.replay_memory.append([state, action, reward, new_state, done])
        self.fit_q_network()
        self.update_target_q_network()
        self.update_count += 1

        if self.update_count % 25 == 0:
            self.fit_dynamics_model()
        if self.update_count % 500 == 0:
            self.eval_dynamics_model()

    def act(self, state):
        self.actions_count += 1
        self.epsilon *= self.epsilon_decay
        self.epsilon = max(self.epsilon_min, self.epsilon)
        if np.random.random() < self.epsilon or self.actions_count < self.initial_random_steps:
            return self.explore(state)
        return np.argmax(self.q_network.predict(state)[0])

    def explore(self,state):
        if not self.dynamics_model_converged:
            return self.get_action_space().sample()

        N = len(self.replay_memory)
        num_samples = 50
        samples = []
        #samples = random.sample(self.replay_memory,num_samples)
        for i in range(N-num_samples,N):
           samples.append(self.replay_memory[i][0])

        best_dist = -np.inf
        best_a = -1
        for action in range(self.get_action_space().n):
            next_state = self.dynamics_model.predict(np.append(state, [[action]], axis=1))

            d = self.get_gaussian_similarity(next_state,samples)

            if d > best_dist:
                best_dist = d
                best_a = action

        return best_a

    def get_mean_distance(self,state, samples):
        num_samples = len(samples)
        d = 0.
        for s in samples:
            d += np.linalg.norm(s - state)
        d /= num_samples
        return d

    def get_gaussian_similarity(self,state, samples):
        d = 0.
        delta = 0.
        sigma = 100.
        for s in samples:
            e = 0.
            for j in range(len(s)):
                e += min(max(((state[0][j] - s[0][j])**2) - delta, 0.),1.)/sigma
            e *= -1.
            d += e
        return -d

    def get_max_distance(self,state,samples):
        return np.max([np.linalg.norm(s - state) for s in samples])

    def init_dynamics_model(self):
        model = Sequential()
        state_shape = (self.get_observation_space().shape[0] + 1,)
        print(state_shape)
        model.add(Dense(24, input_shape=state_shape, activation="relu"))
        model.add(Dense(24, activation="relu"))
        model.add(Dense(self.get_observation_space().shape[0], activation='linear'))
        model.compile(loss="mean_squared_error", optimizer=Adam(lr=self.learning_rate))
        return model

    def fit_dynamics_model(self):
        batchsize = 64
        if len(self.replay_memory) < batchsize:
            return
        samples = self.sample_replays(batchsize)
        sampled_states = []
        sampled_targets = []
        for sample in samples:
            state, action, reward, new_state, done = sample
            input_state = np.append(state, [[action]], axis=1)
            target = new_state
            sampled_states.append(input_state)
            sampled_targets.append(target)

        batched_inputs = np.concatenate(sampled_states, axis=0)
        batched_targets = np.concatenate(sampled_targets, axis=0)
        self.dynamics_model.fit(batched_inputs, batched_targets, epochs=1, verbose=0)

    #debug use only
    def eval_dynamics_model(self):
        samples = self.sample_replays(32)
        sampled_states = []
        sampled_targets = []
        for sample in samples:
            state, action, reward, new_state, done = sample
            input_state = np.append(state, [[action]], axis=1)
            target = new_state
            sampled_states.append(input_state)
            sampled_targets.append(target)

        batched_inputs = np.concatenate(sampled_states, axis=0)
        batched_targets = np.concatenate(sampled_targets, axis=0)
        scores = self.dynamics_model.evaluate(batched_inputs,batched_targets,verbose=0)
        if scores < 0.0003:
            self.dynamics_model_converged = True
            print('Dynamics model has converged!')
        print(self.dynamics_model.metrics_names, scores)