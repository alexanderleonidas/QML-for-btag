import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import pennylane as qml
import matplotlib.pyplot as plt
from dataset import load_dataset
from functools import partial
import jax
from jax.example_libraries.optimizers import adam

def QuantumModel(SEED, TRAIN_SIZE, TEST_SIZE, N_QUBITS, N_LAYERS, LR, N_EPOCHS):
  device = qml.device("default.qubit.jax", wires=N_QUBITS,prng_key = jax.random.PRNGKey(SEED))
  train_features,train_target,test_features,test_target = load_dataset(TRAIN_SIZE,TEST_SIZE,SEED)
  
  @partial(jax.vmap,in_axes=[0,None])
  @qml.qnode(device,interface='jax')
  def circuit(x,w):
    qml.AngleEmbedding(x,wires=range(N_QUBITS))
    qml.StronglyEntanglingLayers(w,wires=range(N_QUBITS))
    return qml.expval(qml.PauliZ(0))

  def loss_fn(w,x,y):
    pred = circuit(x,w)
    return jax.numpy.mean((pred - y) ** 2)
  
  def acc_fn(w,x,y):
    pred = circuit(x,w)
    return jax.numpy.mean(jax.numpy.sign(pred) == y)

  loss_train = partial(loss_fn,x=train_features,y=train_target.to_numpy())
  acc_train = partial(acc_fn,x=train_features,y=train_target.to_numpy())

  loss_test = partial(loss_fn,x=test_features,y=test_target.to_numpy())
  acc_test = partial(acc_fn,x=test_features,y=test_target.to_numpy())

  weights = jax.random.uniform(jax.random.PRNGKey(SEED), (N_LAYERS, N_QUBITS, 3))*jax.numpy.pi

  opt_init, opt_update, get_params = adam(LR)
  opt_state = opt_init(weights)

  #----- Training ------#
  @jax.jit
  def train_step(stepid, opt_state):
    current_w = get_params(opt_state)
    loss_value, grads = jax.value_and_grad(loss_train)(current_w)
    acc_value = acc_train(current_w)
    opt_state = opt_update(stepid, grads, opt_state)
    return loss_value,acc_value, opt_state

  train_loss_data = np.zeros(N_EPOCHS)
  train_acc_data = np.zeros(N_EPOCHS)
  ep = np.linspace(0,N_EPOCHS, num=N_EPOCHS)

  print("Epoch\tLoss\tAccuracy")
  for i in range(N_EPOCHS):
    loss_value,acc_value, opt_state = train_step(i,opt_state)
    train_loss_data[i] = loss_value
    train_acc_data[i] = acc_value
    #if (i+1) % 100 == 0:
        #print(f"{i+1}\t{loss_value:.3f}\t{acc_value*100:.2f}%")
  final_state = opt_state
  
  #------- Testing -------#
  @jax.jit
  def test_step(stepid, opt_state):
    weights = get_params(opt_state)
    loss_value, grads = jax.value_and_grad(loss_test)(weights)
    acc_value = acc_train(weights)
    return loss_value, acc_value

  test_loss_data = np.zeros(N_EPOCHS)
  test_acc_data = np.zeros(N_EPOCHS)

  for i in range(N_EPOCHS):
    loss_value,acc_value = test_step(i,final_state)
    test_loss_data[i] = loss_value
    test_acc_data[i] = acc_value

  return train_loss_data, train_acc_data, test_loss_data, test_acc_data, ep

SEED=0      
TRAIN_SIZE = 60000 
TEST_SIZE = 50000
N_QUBITS = 16   
N_LAYERS = 2
LR=1e-3 
N_EPOCHS = 1000

train_layers_data = np.zeros(10)
test_layers_data = np.zeros(10)
num_layer = np.linspace(1,10, num =10)
for i in range(10):
  train_ld, train_ad, test_ld, test_ad, ep = QuantumModel(SEED, TRAIN_SIZE, TEST_SIZE, N_QUBITS, i, LR, N_EPOCHS)
  train_layers_data[i] = train_ad[-1]
  test_layers_data[i] = test_ad[-1]
plt.title('Accuracy vs Layers')
plt.xlabel("# of layers", sie=14)
plt.ylabel('Accuracy', size=14)
plt.plot(num_layer,train_layers_data,'r',label='Training')
plt.plot(num_layer,test_layers_data,'b', label='Testing')
plt.legend(loc='lower right')
file_name = 'training'+TRAIN_SIZE+'_testing'TEST_SIZE+'.png'
plt.savefig(file_name)
