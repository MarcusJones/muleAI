"""



Needs the AIDataSet

"""
import json

ks.backend.clear_session()
#%% Get a new model folder, if necessary
THIS_MODEL_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d %H%M%S")

#%% Check CUDA
from tensorflow.python.client import device_lib
devices = device_lib.list_local_devices()
for dev in devices:
    print(dev.name)

#%%

class ModelledDataSet(AIDataSet):
    """Augment a dataset with training
    """
    
    def __init__(self,path_data,data_folder,model_folder):
        super().__init__(path_data,data_folder)
        
        self.model_folder = model_folder
        
        
        # Create the model folder, or reference it
        self.path_model_dir = os.path.join(self.path_data,self.data_folder,self.model_folder)
        if not os.path.exists(self.path_model_dir):
            os.makedirs(self.path_model_dir)
            logging.debug("Created a NEW model folder at {}/{}".format(data_folder,self.model_folder))
        else:
            logging.debug("Model folder at {}/{}".format(data_folder,model_folder))
            
        #assert not os.listdir(self.path_model_dir), "{} not empty".format(self.path_model_dir)
        #logging.debug("This model exists in {}".format(model_dir))
        
        if not self.model_folder_empty:
            self.list_models()

    def list_models(self):
        search_str = os.path.join(self.path_model_dir,'*.h5')
        #print(search_str)
        paths_weights = glob.glob(search_str)
        logging.debug("{} weights found".format(len(paths_weights)))
        model_files = list()
        for this_wt_path in paths_weights:
            _,fname = os.path.split(this_wt_path)
            basename, ext = os.path.splitext(fname)
            #print(basename)
            loss_string = re.search(r"Loss [-+]?[0-9]*\.?[0-9]+",basename)[0]
            loss_num = float(re.search("[-+]?[0-9]*\.?[0-9]+",loss_string)[0])            
            #print(loss_num)
            model_files.append({'path':this_wt_path, 'loss':loss_num, 'fname':basename})
        
        model_files = sorted(model_files, key=lambda k: k['loss'])
        for mf in model_files:
            #print(mf['fname'],mf['loss'])
            pass
        return model_files
            
    @property
    def model_folder_empty(self):
        if os.listdir(self.path_model_dir): return False
        else:  return True
    
    @property
    def has_predictions(self):
        return 'steering_pred_signal' in self.df.columns
    
    def generate_partitions(self, split=0.8):
        msk = np.random.rand(len(self.df)) < split
        self.partition = dict()
        self.partition['train'] = self.df.index[msk].values
        self.partition['validation'] = self.df.index[~msk].values
        logging.debug("Train/val partition set to {:0.0f}/{:0.0f}%".format(split*100, (1-split)*100))
    
    def instantiate_generators(self,generator_class, generator_params = None):
        if not generator_params:
            generator_params = {'dim': (160,120),
                      'batch_size': 64,
                      'n_classes': 15,
                      'n_channels': 3,
                      'shuffle': True,
                      #'path_frames':os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'camera_numpy.zip'),
                      #'path_records':os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'df_record.pck'),
                     }
       
        self.training_generator = generator_class(self.partition['train'], data1, **generator_params)
        self.validation_generator = generator_class(self.partition['validation'], data1, **generator_params)        
        logging.debug("training_generator and validation_generator instantiated".format())

    def instantiate_model(self):
        def baseline_steering_model():
            model = ks.models.Sequential()
            model.add(ks.layers.Conv2D(24, (5,5), strides=(2, 2), activation = "relu", input_shape=(120,160,3)))
            model.add(ks.layers.Conv2D(32, (5,5), strides=(2, 2), activation = "relu"))
            model.add(ks.layers.Conv2D(64, (5,5), strides=(2, 2), activation = "relu"))
            model.add(ks.layers.Conv2D(64, (3,3), strides=(2, 2), activation = "relu"))
            model.add(ks.layers.Conv2D(64, (3,3), strides=(1, 1), activation = "relu"))
            model.add(ks.layers.Flatten()) # This is just a reshape!
            model.add(ks.layers.Dense(100,activation="relu"))
            model.add(ks.layers.Dropout(0.1))
            model.add(ks.layers.Dense(50,activation="relu"))
            model.add(ks.layers.Dropout(0.1))
            model.add(ks.layers.Dense(15, activation='softmax', name='angle_out'))
            return model
        optimizer = ks.optimizers.Adam(lr=0.001, beta_1=0.99, beta_2=0.999, epsilon=None, decay=0.0, amsgrad=False)
        
        model = baseline_steering_model()
        model.compile(optimizer=optimizer,
                        loss='categorical_crossentropy',
                        metrics=[ks.metrics.categorical_accuracy]
                       )
        
        self.model = model
        logging.debug("Model created".format())
        
    def instantiate_callbacks(self):
        # Save checkpoint
        weight_filename="weights Loss {val_loss:.2f} Epoch {epoch:02d}.h5"
        weight_path = os.path.join(self.path_model_dir,weight_filename)
        callback_wts = ks.callbacks.ModelCheckpoint(weight_path, 
                                                        monitor='val_loss', 
                                                        verbose=1, 
                                                        save_best_only=True, 
                                                        mode='min')
        # Early stopping
        callback_stopping = ks.callbacks.EarlyStopping(monitor='val_loss', 
                                                       min_delta=0.0005, 
                                                       patience=5, # number of epochs with no improvement after which training will be stopped.
                                                       verbose=1, 
                                                       mode='auto')
        
        # Logger
        this_log_path = os.path.join(self.path_model_dir,"history.log".format())
        callback_logger = ks.callbacks.CSVLogger(this_log_path,separator=',', append=True)
        
        
        class MyCallback(ks.callbacks.Callback):
            def __init__(self,model_folder_path):
                self.model_folder_path = model_folder_path
                
            def on_train_begin(self, logs={}):
                logging.info("Started training {}".format(self.model))
                self.losses = []
                return 
                
            def on_train_end(self, logs={}):
                logging.info("Finished training {}".format(self.model))
                return
         
        
            def on_epoch_begin(self, epoch, logs={}):
                logging.info("Epoch {} {}".format(epoch,logs))
                return
         
            def on_batch_end(self, batch, logs={}):
                #self.losses.append(logs.get('loss'))
                logging.debug("\tBatch {} {}".format(batch,logs))
                pass
        
                
            def on_epoch_end(self, epoch, logs={}):
                #print("HISTORY:{}".format(self.model.history.history))
                #print("EPOCH:", epoch)
                #print("LOGS:",logs)
                
                
                this_path = os.path.join(self.model_folder_path,"History epoch {:02d}.json".format(epoch))
                with open(this_path, 'w') as fh:
                    json.dump(self.model.history.history, fh)
                print("Saved history to {}".format(this_path))

                
        my_history_callback = MyCallback(self.path_model_dir)
        self.callback_list = [my_history_callback, callback_wts,callback_stopping,callback_logger]        
        
        logging.debug("{} callbacks created".format(len(self.callback_list)))

    def train_model(self, epochs=10):
        assert self.model_folder_empty, "The model folder {} is not empty, instantiate a new model!".format(self.model_folder)        
        with LoggerCritical():
            history = self.model.fit_generator(
                    generator=self.training_generator,
                    validation_data=self.validation_generator,
                    use_multiprocessing=True,
                    workers=6,
                    epochs=epochs,
                    verbose=1,
                    callbacks=self.callback_list)
        
        self.history_dict = history.__dict__
        
        #this_timestamp = datetime.datetime.now().strftime("%Y%m%d %H%M%S")
        logging.debug("Finished training model {}".format(self.model_folder))

    def load_best_model(self):
        model_def = self.list_models()[0]
        path_model = model_def['path']
        assert os.path.exists(path_model)
        
        self.model = ks.models.load_model(path_model)
        
        logging.debug("Loaded weights {} with loss {}".format(model_def['fname'],model_def['loss']))

    def load_spec_model(self,model_id=None):
        # Load a specific weights file
        raise
        logging.debug("Loading model {} from {}".format(model_id, path_model))
        path_model = os.path.join(self.path_model_dir,model_id)
        pred_model = ks.models.load_model(path_model)
        
    #def make_predictions(self,model_id=None):
    #    logging.debug("Predicting over self.model {}".format(self.model))
        #self.make_model_predictions(self.model)
        
    def make_predictions(self):
        """Augment the df_records with the predictions
        """
        #print(self.df.head())
        #this_df_records['steering_pred_cats'] = pd.Series(dtype=object)
        #df_records['steering_pred_argmax'] = 
        
        # get all the X array (all numpy arrays), in *proper* order
        
        #
        logging.debug("Predicting over self.model {}".format(self.model))

        npz_file = np.load(self.path_frames_npz)
        #frames_array = np.stack([npz_file[idx] for idx in batch_indices], axis=0)
        frames_array = np.stack([npz_file[idx] for idx in self.df.index], axis=0)
        #print(arrays)
        logging.debug("All images loaded as 1 numpy array {}".format(frames_array.shape))
        logging.debug("Starting predictions ...".format(frames_array.shape))
        
        #predictions_cats = self.model.predict(frames_array,verbose=1)
        predictions_cats = self.model.predict(frames_array,verbose=1)
        
        logging.debug("Predictions complete, shape: {}".format(predictions_cats.shape))
        #logging.debug("Saved categories to column steering_pred_signal_cats".format())
        
        predictions = self.unbin_Y(predictions_cats)
        #logging.debug("Predictions unbinned, shape: {}".format(predictions.shape))
        
        self.df['steering_pred_signal'] = predictions
        logging.debug("Predictions added to df in column {}".format('steering_pred_signal'))
        
        # Get the category of this steering signal
        self.df['steering_pred_signal_catnum'] = self.signal_to_category_number('steering_pred_signal')
        
        self.raw_accuracy =  sum(self.df['steering_signal_catnum'] == self.df['steering_pred_signal_catnum'])/len(self.df)
        logging.debug("Raw accuracy {:0.2f}%".format(self.raw_accuracy*100))
        
        #return predictions

    def save_predictions(self,path_out):
        assert 'steering_pred_signal' in self.df.columns 
        assert 'steering_pred_signal_catnum' in self.df.columns 
        pass

#%% RELOAD A MODEL
LOCAL_PROJECT_PATH = glob.glob(os.path.expanduser('~/MULE DATA'))[0]
THIS_DATASET = "20180904 192907"
THIS_MODEL_ID = 'model 20180906 154310'
trds = ModelledDataSet(LOCAL_PROJECT_PATH,THIS_DATASET,THIS_MODEL_ID)
trds.load_best_model()
trds.model.summary()
trds.make_predictions()


        
#%% CREATE NEW MODEL AND TRAIN

#trained_dataset = ModelledDataSet(LOCAL_PROJECT_PATH,THIS_DATASET,'model ' + THIS_MODEL_TIMESTAMP)
THIS_MODEL_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d %H%M%S")

trds = ModelledDataSet(LOCAL_PROJECT_PATH,THIS_DATASET,'model ' + THIS_MODEL_TIMESTAMP)
trds.model_folder_empty
trds.generate_partitions()
#trained_dataset.list_models()
trds.instantiate_generators(MuleDataGenerator)
trds.instantiate_model()
trds.model.summary()
trds.instantiate_callbacks()
trds.train_model(3)
trds.make_predictions()

#%% Plot analysis of model

def plot_hist(history_dict, accuracy_name, model_title):
    #fig = plt.figure(figsize=(5,4))
    #fig=plt.figure(figsize=(20, 10),facecolor='white')

    #f, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 5),sharey=False,facecolor='white')
    bgcolor = '0.15'
    bgcolor = 'white'
    f, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 5),sharey=False,facecolor=bgcolor)
    
    ax1.plot(history_dict['epoch'],  history_dict['history']['loss'],label="Train")
    ax1.plot(history_dict['epoch'],  history_dict['history']['val_loss'],label="CV")
    ax1.set_title("Loss function development - Training set vs CV set")
    ax1.legend(loc='upper right')
    ax1.set_xlabel('Epochs')
    ax1.set_ylabel('Values')
    
    ax2.plot(history_dict['epoch'],  history_dict['history'][accuracy_name],label="Train")
    ax2.plot(history_dict['epoch'],  history_dict['history']['val_'+accuracy_name],label="CV")
    ax2.set_title("Accuracy development - Training set vs CV set")
    ax2.legend(loc='upper right')
    ax2.set_xlabel('Epochs')
    ax2.set_ylabel('Values')
    
    plt.suptitle(model_title, fontsize=16)
    
    plt.show()


# Plot training history
#%matplotlib inline
#model_title = "10 Epochs"

plot_hist(history_dict,'categorical_accuracy',model_title="")

# Plot a few samples
# TURN OFF PLOTTING
#%matplotlib inline

# Right turn
these_indices = df_records[df_records['steering_signal'] > 0.9].sample(4)['timestamp'].tolist()
these_records = get_full_records(frames_npz, df_records, these_indices)
plot_frames(these_records)

# Left turn
these_indices = df_records[df_records['steering_signal'] < -0.9].sample(4)['timestamp'].tolist()
these_records = get_full_records(frames_npz, df_records, these_indices)
plot_frames(these_records)

# Straight
these_indices = df_records[(df_records['steering_signal'] > -0.1) & (df_records['steering_signal'] < 0.1)].sample(4)['timestamp'].tolist()
these_records = get_full_records(frames_npz, df_records, these_indices)
plot_frames(these_records)


#%% Saving the model
## Save the model weights, architecture, configuration, and state
## serialize weights to HDF5
#path_model_h5 = os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'model',this_timestamp + ' model.h5')
#blmodel.save(path_model_h5)
#logging.debug("Saved complete model hd5 to disk".format())
#
## Save just the architecture to JSON
#path_model_json = os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'model',this_timestamp + ' model.json')
#model_json = blmodel.to_json()
#with open(path_model_json, "w") as json_file:
#    json_file.write(model_json)
#logging.debug("Saved model configuration json to disk".format())
#
## Save the history to JSON
#path_history_json = os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'model',this_timestamp + ' history.json')
#with open(path_history_json, "w") as json_file:
#    if 'model' in history_dict: 
#        history_dict.pop('model')
#    json.dump(history_dict,json_file)
#logging.debug("Saved model history json to disk".format())
#
## Save the predicted dataframe
#path_records_json = os.path.join(LOCAL_PROJECT_PATH,THIS_DATASET,'model',this_timestamp + ' predicted.pck')
#df_records.to_pickle(path_records_json)




