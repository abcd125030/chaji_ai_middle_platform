import os
import uuid
import shutil
import tempfile
import gc
import fitz
import torch
import base64
import filetype
import litserve as ls
from pathlib import Path
from fastapi import HTTPException


class MinerUAPI(ls.LitAPI):
    def __init__(self, output_dir='/home/lisongming/tmp'):
        self.output_dir = Path(output_dir)
        self.max_batch_size = 32
        self.enable_async = False
        self.batch_timeout = 60  # 批处理超时时间（秒）
        self.request_timeout = 120  # 请求超时时间（秒）

    def setup(self, device):
        if device.startswith('cuda'):
            os.environ['CUDA_VISIBLE_DEVICES'] = device.split(':')[-1]
            if torch.cuda.device_count() > 1:
                raise RuntimeError("Remove any CUDA actions before setting 'CUDA_VISIBLE_DEVICES'.")

        from magic_pdf.tools.cli import do_parse, convert_file_to_pdf
        from magic_pdf.model.doc_analyze_by_custom_model import ModelSingleton

        self.do_parse = do_parse
        self.convert_file_to_pdf = convert_file_to_pdf

        model_manager = ModelSingleton()
        model_manager.get_model(True, False)
        model_manager.get_model(False, False)
        print(f'Model initialization complete on {device}!')

    def decode_request(self, request):
        file = request['file']
        pdf_name = ""
        if 'pdf_name' in request:
            pdf_name = request['pdf_name']
        file = self.cvt2pdf(file)
        opts = request.get('kwargs', {})
        opts.setdefault('debug_able', False)
        opts.setdefault('parse_method', 'auto')
        return file, opts, pdf_name

    def predict(self, inputs):
        try:
            if not input or not isinstance(inputs, (list, tuple)):
                raise ValueError("输入参数格式错误")
            # inputs = [(b'%PDF-1.7\n%\xc2\xb3\xc7\xd8\r\n3 0 obj\rstartxref\r27764\r%%EOF\r',{'debug_able': False, 'parse_method': 'auto'}, "6e4e4c8a-d5f2-4970-906e-908472cbc240")] 
            print(f'predict is begin!')
            if inputs[0][2] != "":
                pdf_name = inputs[0][2]
                print("inputs[0][2]: " + pdf_name)
            else:
                pdf_name = str(uuid.uuid4())
                print("uuid.uuid4(): " + pdf_name)
            output_dir = self.output_dir.joinpath(pdf_name)
            os.makedirs(output_dir, exist_ok=True)
            self.do_parse(self.output_dir, pdf_name, inputs[0][0], [], **inputs[0][1])
            return [str(output_dir)]
        except Exception as e:
            print(f'predict is error!')
            shutil.rmtree(output_dir, ignore_errors=True)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            self.clean_memory()
            
    def encode_response(self, response):
        return {'output_dir': response}

    def clean_memory(self):
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()

    def cvt2pdf(self, file_base64):
        try:
            temp_dir = Path(tempfile.mkdtemp())
            temp_file = temp_dir.joinpath('tmpfile')
            file_bytes = base64.b64decode(file_base64)
            file_ext = filetype.guess_extension(file_bytes)

            if file_ext in ['pdf', 'jpg', 'png', 'doc', 'docx', 'ppt', 'pptx']:
                if file_ext == 'pdf':
                    return file_bytes
                elif file_ext in ['jpg', 'png']:
                    with fitz.open(stream=file_bytes, filetype=file_ext) as f:
                        return f.convert_to_pdf()
                else:
                    temp_file.write_bytes(file_bytes)
                    self.convert_file_to_pdf(temp_file, temp_dir)
                    return temp_file.with_suffix('.pdf').read_bytes()
            else:
                raise Exception('Unsupported file format')
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    server = ls.LitServer(
        MinerUAPI(output_dir='/home/lisongming/tmp'),
        accelerator='cuda',
        devices='auto',
        workers_per_device=1,
        timeout=False
    )
    
    # 获取FastAPI应用实例
    app = server.app
    
    @app.get("/download_output_files")
    async def download_output_files():
        return {"download_output_files": 1001}
        
    server.run(port=8002)
    # import uvicorn
    # uvicorn.run(app, host='0.0.0.0', port=8002, workers=4)
