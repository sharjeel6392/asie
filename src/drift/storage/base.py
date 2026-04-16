class DriftStore:
    def fetch_current(self, start_time: str, end_time: str):
        '''
        Fetch data for drift analysis. This is a stub and should be
        implemented to fetch from your actual data store.
        '''
        raise NotImplementedError('fetch_current method not implemented')
    
    def fetch_reference(self, start_time: str, end_time: str):
        '''
        Fetch reference data for drift analysis.
        This is a stub and should be implemented to fetch from your actual
        data store.
        '''
        raise NotImplementedError('fetch_reference method not implemented')