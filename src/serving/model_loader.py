class ModelLoader:
    def __init__(self):
        self.model = None
        self.tokenizer = None

    def load(self):
        """
        Load model + tokenizer here.
        """
        print('ModelLoader.load() called')
        self.model = "stub-model"
        self.tokenizer = "stub-tokenizer"
    
    def is_ready(self):
        return self.model is not None