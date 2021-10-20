import csv

class CSVReader:
    "Read test data from csv file using an iterator"

    def __init__(self, file, reuse):
        try:
            file = open(file)
        except TypeError:
            pass  # "file" was already a pre-opened file-like object
        self.file = file
        self.reader = csv.reader(file)
        self.reuse = reuse

    def __next__(self):
        try:
            # next(self.reader)
            return next(self.reader)
        except StopIteration:
            # reuse file on EOF
            if self.reuse:
                self.file.seek(0, 0)
                next(self.reader)
                return next(self.reader)
            else:
                # sys.exit()
                return False


class validate_test_data:
    def __init__(self, reuse_data_on_eof, test_data_path, requested_num_of_users):
        self.reuse_data_on_eof = reuse_data_on_eof
        self.test_data_path = test_data_path
        self.requested_num_of_users = requested_num_of_users


    def csv_data(self):
        if not self.reuse_data_on_eof:
            csv_data = CSVReader(self.test_data_path, reuse=self.reuse_data_on_eof)
            global cnt
            cnt = 0
            next(csv_data)
            while next(csv_data):
                cnt += 1
            if cnt < self.requested_num_of_users:
                return 0
            else:
                return 1
        else:
            return 1

    def get_headers(self):
        csv_data = CSVReader(self.test_data_path, reuse=self.reuse_data_on_eof)
        data = next(csv_data)
        init_data = 'csv_data_variable = next(pull_source_data)\n'
        idx = 0
        for r in data:
            init_data += "        self." + r + " = csv_data_variable[" + str(idx) + "]"
            if idx+1 != len(data):
                init_data += "\n"
            idx += 1
        return init_data+'\n'
