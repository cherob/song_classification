

from cfg import Config
import pandas as pd
import time
import pickle
import matplotlib.pyplot as plt
from matplotlib import cm
import glob
from keras.optimizers import SGD
from keras.utils import to_categorical
from keras.models import Model, load_model, save_model, Sequential
from keras.callbacks import ModelCheckpoint
from keras.layers import Dropout, Dense, TimeDistributed, Conv2D, MaxPool2D, Flatten, LSTM, Masking
from keras.backend.tensorflow_backend import set_session
from sklearn.utils import shuffle
from python_speech_features import mfcc, logfbank
import tensorflow as tf
import json
from tqdm import tqdm
import sys
import os
import pickle
import os
import numpy as np
from scipy.io import wavfile
from sklearn.utils import shuffle
from sklearn.metrics import accuracy_score

print(" Genre Classification")
print("  by Robin Seerig")


# ######################################################### #
#   Setup
# ######################################################### #

# Config File

config = Config()


def saveConfig(x):
    path = os.path.join(x.p_date_dir_path, str(abs(x.id)) + '.p')
    print(" ...config saved ({})".format(x.id))
    with open(path, 'wb') as handle:
        pickle.dump(x, handle, protocol=4)

# ######################################################### #
#   Getters
# ######################################################### #


def getMaximumData():
    data = (config.max_class_files * config.cat * config.max_tack_samples)
    return int(data)


def getMaximumSamples():
    return int((config.audio_length) / config.sample_length)


def getRefactoredData(data):
    data_x1 = data/config.cat
    data_x2 = int(data_x1)
    data_x3 = data_x2*config.cat
    return int(data_x3)


def getSmallestDataset():
    minorityFiles = sys.maxsize

    for class_name in classes:
        files = len(df[df.label == class_name].index)
        if (minorityFiles > files):
            minorityFiles = files
    return minorityFiles


def getConfigFile(path):
    with open(path, 'rb') as handle:
        config = pickle.load(handle)
        return config


def getTemporaryData():
    for file in glob.glob(os.path.join(config.p_date_dir_path, '*')):
        conf = getConfigFile(file)
        config.id = 1
        conf.id = 1
        importance = ["use_random_in_feat", "nfilt", "nfeat", "nfft", "frame_rate", "sample_length", "audio_length",
                      "audio_startpoint", "validation_data_mult", "cat",  "max_class_files"]
        for prop in importance:

            try:
                if getattr(conf, prop) == False:
                    conf.id = conf.id * len(prop)
                elif getattr(conf, prop) == True:
                    conf.id = conf.id / len(prop)
                else:
                    conf.id = conf.id + getattr(conf, prop)*10

                if getattr(config, prop) == False:
                    config.id = config.id * len(prop)
                elif getattr(config, prop) == True:
                    config.id = config.id / len(prop)
                else:
                    config.id = config.id + getattr(config, prop)*10
                conf.id = round(conf.id)+1
                config.id = round(config.id)+1
                # print(prop,conf.id, config.id, " | ",getattr(conf, prop), getattr(config, prop))
            except:
                config.id = config.id * len(prop)
                conf.id = conf.id * len(prop)
        if conf.id == config.id:
            print(" - Loaded config with id: {}".format(conf.id))
            return conf
    print(" - Your config id: {}".format(config.id))
    return None


def getLastModelFilename():
    for file in glob.glob(os.path.join(config.model_date_dir_path, '*')):
        if file == os.path.join(config.model_date_dir_path, str(abs(config.id))+'.model'):
            return file


def getConvModel(shape):
    model = Sequential()
    model.add(Conv2D(16, (3, 3), activation='relu', strides=(
        1, 1), padding='same', input_shape=shape))
    model.add(Conv2D(32, (3, 3), activation='relu',
                     strides=(1, 1), padding='same'))
    model.add(Conv2D(64, (3, 3), activation='relu',
                     strides=(1, 1), padding='same'))
    model.add(Conv2D(128, (3, 3), activation='relu',
                     strides=(1, 1), padding='same'))

    model.add(MaxPool2D((2, 2)))
    model.add(Dropout(0.5))
    model.add(Flatten())
    model.add(Dense(128, activation='relu'))
    model.add(Dense(64, activation='relu'))
    model.add(Dense(config.cat, activation='softmax'))
    model.summary()

    # compile model
    model.compile(loss='categorical_crossentropy',
                  optimizer='adam', metrics=['acc'])

    return model


def getRandomSamples(datasets):
    X = []
    y = []
    datasets = getRefactoredData(datasets)
    _min, _max = float('inf'), -float('inf')

    pbar1 = tqdm(total=datasets, position=0)
    for _ in range(int(datasets/3)):
        for class_index in classes:
            # pick random file with rand class
            file = np.random.choice(df[df.label == class_index].index)

            rate, wav = wavfile.read(os.path.join(
                config.refactored_audio_dir, file))

            if wav.shape[0] == 0:
                print('ERROR')
                continue

            # grab point on fiile
            rand_index = np.random.randint(0, wav.shape[0]-config.step)

            # create smaple "config.step" steps long
            sample = wav[rand_index:rand_index+config.step]

            # create matix sample (convert that sample)
            X_sample = mfcc(sample, rate,
                            numcep=config.nfeat, nfilt=config.nfilt, nfft=config.nfft).T
            _min = min(np.amin(X_sample), _min)
            _max = max(np.amax(X_sample), _max)
            # X.append(X_sample if config.mode == 'conv' else X_sample.T)
            X.append(X_sample)
            y.append(classes.index(class_index))

            pbar1.update(1)

    config.min = _min
    config.max = _max

    # create numpy array
    X, y = np.array(X), np.array(y)

    # reshape numpy array
    X = (X - _min) / (_max - _min)

    X = X.reshape(X.shape[0], X.shape[1],  X.shape[2], 1)
    y = to_categorical(y, num_classes=config.cat)

    pbar1.close()

    return X, y


def getFixedSamples(datasets):
    X = []
    y = []
    datasets = getRefactoredData(datasets)
    files = int((datasets / config.max_tack_samples) / config.cat)
    _min, _max = float('inf'), -float('inf')

    pbar1 = tqdm(total=datasets, position=0)
    for file_index in range(files):
        for class_index in classes:

            # pick file with class
            file = df[df.label == class_index].index[file_index]

            rate, wav = wavfile.read(os.path.join(
                config.refactored_audio_dir, file))
            # print(index, selected_class, rate, file)

            if wav.shape[0] == 0:
                print('ERROR')
                continue

            for audio_index in range(config.max_tack_samples):
                pbar1.update(1)
                # create smaple "config.step" steps long
                sample = wav[audio_index:audio_index+config.step]

                # create matix sample (convert that sample)
                X_sample = mfcc(sample, rate,
                                numcep=config.nfeat, nfilt=config.nfilt, nfft=config.nfft).T

                _min = min(np.amin(X_sample), _min)
                _max = max(np.amax(X_sample), _max)
                X.append(X_sample)
                y.append(classes.index(class_index))

    config.min = _min
    config.max = _max

    # create numpy array
    X, y = np.array(X), np.array(y)

    # reshape numpy array
    X = (X - _min) / (_max - _min)

    X = X.reshape(X.shape[0], X.shape[1],  X.shape[2], 1)
    y = to_categorical(y, num_classes=config.cat)

    pbar1.close()

    return X, y


# ######################################################### #
#   Builders
# ######################################################### #


def buildSamples(datasets, last_config):
    if config.use_random_in_feat:
        print(" -> building {} random prediction samples".format(datasets))
        X, y = getRandomSamples(datasets)
    else:
        print(" -> building {} fixed prediction samples".format(datasets))
        X, y = getFixedSamples(datasets)

    config.data = [X, y]

    saveConfig(config)

    return X, y


def buildPredctions(datasets, last_config):
    y_pred = []

    print(" -> building {} fixed prediction samples".format(datasets))
    y_prob, y_true = getFixedSamples(datasets)
    for x in y_prob:
        x = x.reshape(1, x.shape[0], x.shape[1], 1)
        y_hat = model.predict(x)
        y_pred.append(np.mean(y_hat))

    return y_true, y_pred, y_prob



def buildValidationSamples(datasets, last_config):
    if config.use_checkpoints:
        try:
            if last_config.vdata:
                _X = last_config.data[0],
                _y = last_config.data[1]
                if config.use_random_in_feat:
                    print(" -> loaded {} random validation samples".format(datasets))
                else:
                    print(" -> loaded {} fixed validation samples".format(datasets))
                return _X, _y
        except:
            None

    datasets = datasets*config.validation_data_mult

    if config.use_random_in_val_feat:
        print(" -> building random validation samples")
        X, y = getRandomSamples(datasets)
    else:
        print(" -> building fixed validation samples")
        X, y = getFixedSamples(datasets)

    config.vdata = [X, y]

    saveConfig(config)

    return X, y


# ######################################################### #
#   Functions
# ######################################################### #

def drawStatistics(acc_temp, val_acc_temp, loss_temp, val_loss_temp):
    # Plot prediction & validation accuracy values
    plt.plot(acc_temp)
    plt.plot(val_acc_temp)
    plt.title('Model accuracy')
    plt.ylabel('Accuracy')
    plt.xlabel('Epoch')
    plt.legend(['Train', 'Test'], loc='upper left')

    plt.savefig(os.path.join(config.img_dir, str(abs(config.id)) + 'acc.png'))
    plt.close()

    # Plot prediction & validation loss values
    plt.plot(loss_temp)
    plt.plot(val_loss_temp)
    plt.title('Model loss')
    plt.ylabel('Loss')
    plt.xlabel('Epoch')
    plt.legend(['Train', 'Test'], loc='upper left')

    plt.savefig(os.path.join(config.img_dir, str(abs(config.id)) + 'loss.png'))
    plt.close()


def fitModel(model, X, y, val_X, val_y):
    try:
        if config.acc_temp == None:
            config.acc_temp = []
            config.val_acc_temp = []
            config.loss_temp = []
            config.val_loss_temp = []
    except:
        config.acc_temp = []
        config.val_acc_temp = []
        config.loss_temp = []
        config.val_loss_temp = []

    if config.calls is False:
        config.calls = sys.maxsize
    checkpoint = None
    if config.use_checkpoints:
        path = getLastModelFilename()
        try:
            model = load_model(path)
            print(" -> Continue prediction")
        except:
            pass

    for index in range(config.calls):

        if(config.calls == sys.maxsize):
            print("Call {}".format(index+1))
        else:
            print("Call {}/{}".format(index+1, config.calls))

        drawStatistics(config.acc_temp, config.val_acc_temp,
                       config.loss_temp, config.val_loss_temp)

        print(" -> Shuffle model")
        X, y = shuffle(X, y, random_state=0)
        val_X, val_y = shuffle(X, y, random_state=0)

        checkpoint = model.fit(X, y, epochs=config.epochs, validation_data=(
            val_X, val_y), shuffle=True, batch_size=config.batch_size, verbose=1)

        config.acc_temp = config.acc_temp + checkpoint.history['acc']
        config.val_acc_temp = config.val_acc_temp + \
            checkpoint.history['val_acc']
        config.loss_temp = config.loss_temp + checkpoint.history['loss']
        config.val_loss_temp = config.val_loss_temp + \
            checkpoint.history['val_loss']

        if config.use_evaluate is True:
            print(" - Evaluate...")
            score = model.evaluate(X, y, batch_size=config.batch_size)

            print(" => [Score] = {}".format(score))

        model.save(os.path.join(config.model_date_dir_path,
                                str(abs(config.id)) + '.model'))
        saveConfig(config)


def calculateConfigData():
    if config.cat is False:
        config.cat = len(classes)
    else:
        if config.cat > len(classes):
            print(" - config.cat ({}) is to large, expected ({})".format(
                config.cat, len(classes)))
            config.cat = len(classes)

    if config.max_class_files is False:
        config.max_class_files = getSmallestDataset()
    else:
        if config.max_class_files > getSmallestDataset():
            print(" - config.max_class_files ({}) is to large, expected ({})".format(
                config.max_class_files, getSmallestDataset()))
            config.max_class_files = getSmallestDataset()

    if config.max_tack_samples is False:
        config.max_tack_samples = getMaximumSamples()
    else:
        if config.max_tack_samples > getMaximumSamples():
            print(" - config.max_tack_samples ({}) is to large, expected ({})".format(
                config.max_tack_samples, getMaximumSamples()))
            config.max_tack_samples = getMaximumSamples()

    if config.max_data is False:
        config.max_data = getMaximumData()
    else:
        if config.max_data > getMaximumData():
            print(" - config.max_data ({}) is to large, expected ({})".format(
                config.max_data, getMaximumData()))
            config.max_data = getMaximumData()

    h1 = config.audio_startpoint/60
    m1 = h1*60-(int(h1)*60)
    h2 = (config.audio_startpoint + config.audio_length)/60
    m2 = h2*60-(int(h2)*60)

    print(" {} loaded categories".format(config.cat))
    print("   with  {} files each,".format(config.max_class_files))
    print("   cut from {:0>2}:{:0>2} to {:0>2}:{:0>2},".format(
        int(h1), int(m1), int(h2), int(m2)))
    print("   divided into {} samples".format(config.max_tack_samples))
    print("   with a length of {} seconds each,".format(config.sample_length))
    print(" -> results in {} data records".format(config.max_data))

# ######################################################### #
#   Code
# ######################################################### #


print("=== Loading model ===")
model = load_model(config.model_path)
model.summary()

print("=== Load table with classified songs ===")
df = pd.read_csv(config.refactored_audio_date_path)
df.set_index('fname', inplace=True)
df.to_csv(config.model_audio_date_path)
classes = list(np.unique(df.label))
# fn2class = dict(zip(df.fname, df.label))
print(" - Following classes are available: {}".format(classes))

print("=== Calculate maximum data ===")
calculateConfigData()

print("=== Get config ===")
last_config = getTemporaryData()

print("=== Building predictions ===")
y_true, y_pred, fn_prob = buildPredctions(config.max_data, last_config)

print("=== Calculate accuracy score ===")
acc_score = accuracy_score(y_true=y_true, y_pred=y_pred)
print(" - Accuracy score: {}".format(acc_score))


print("=== Format predictions ===")

# y_probs = []
# for i, row in df.iterrows():
#     y_prob = fn_prob[row.fname]
#     y_probs.append(y_prob)
#     for c, p in zip(classes, y_prob):
#         df.at[i, c] = p

# y_pred = [classes[np.argmax(y)] for y in y_probs]
df['y_pred'] = y_pred

df.to_csv(config.predictions_date_path, sep=";", index=False)
