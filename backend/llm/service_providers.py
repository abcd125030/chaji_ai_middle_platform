from abc import ABC, abstractmethod


# 抽象类 BaseModelServiceProvider
class BaseModelServiceProvider(ABC):
    @abstractmethod
    def send_request(self, model_name, model_endpoint, model_key, model_id, service_target, user_id, payload, params):
        pass

    @abstractmethod
    def write_qa_to_session(self, model_name, session, payload, params, response, deal_response):
        pass

    @abstractmethod
    def send_customization_request(self, model_name, model_endpoint, model_key, model_id, service_target, user_id,
                                   payload, params):
        pass

    @abstractmethod
    def send_customization_picture_request(self, model_name, model_endpoint, model_key, model_id, service_target,
                                           user_id, payload, params):
        pass

    @abstractmethod
    def write_qa_to_customization(self, model_name, user_id, service_target, srcpayload, payload, params, response_json,
                                  deal_response, output, is_final, input_session_length, output_session_length):
        pass
