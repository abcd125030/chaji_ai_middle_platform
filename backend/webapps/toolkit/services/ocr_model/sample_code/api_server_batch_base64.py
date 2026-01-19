"""
DeepSeek-OCR API Server with Batch Base64 Support
支持批量多张图片输入，使用base64传输
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from vllm import LLM, SamplingParams
from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor
from PIL import Image
from enum import Enum
from typing import List, Optional
import base64
import io
import uvicorn
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(filename)s:%(lineno)d: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="DeepSeek-OCR API", version="2.0.0")

# 定义 OCR 模式
class OCRMode(str, Enum):
    FREE_OCR = "free_ocr"
    CONVERT_TO_MARKDOWN = "convert_to_markdown"
    PARSE_FIGURE = "parse_figure"
    LOCATE_OBJECT = "locate_object"

# 模式对应的 prompt
MODE_PROMPTS = {
    OCRMode.FREE_OCR: "<image>\nFree OCR.",
    OCRMode.CONVERT_TO_MARKDOWN: "<image>\n<|grounding|>Convert the document to markdown.",
    OCRMode.PARSE_FIGURE: "<image>\nParse Figure.",
    OCRMode.LOCATE_OBJECT: "<image>\nLocate Object by Reference: {reference}",
}

# 请求模型
class OCRRequest(BaseModel):
    images: List[str] = Field(..., description="Base64编码的图片列表")
    mode: OCRMode = Field(default=OCRMode.CONVERT_TO_MARKDOWN, description="OCR模式")
    custom_prompt: Optional[str] = Field(default=None, description="自定义prompt（可选）")
    reference: Optional[str] = Field(default=None, description="用于locate_object模式的参考文本")
    max_tokens: int = Field(default=8192, description="最大token数", ge=1, le=32768)
    temperature: float = Field(default=0.0, description="温度参数", ge=0.0, le=2.0)

# 响应模型
class OCRResult(BaseModel):
    result: str
    mode: str
    prompt: str
    image_size: List[int]

class OCRBatchResponse(BaseModel):
    results: List[OCRResult]
    total: int
    success_count: int
    failed_count: int

# 初始化模型
logger.info("Initializing DeepSeek-OCR model...")
llm = LLM(
    model="/mnt/models/DeepSeek-OCR",
    enable_prefix_caching=False,
    mm_processor_cache_gb=0,
    logits_processors=[NGramPerReqLogitsProcessor],
    trust_remote_code=True,
    dtype="bfloat16",
    gpu_memory_utilization=0.9,
)
logger.info("Model initialized successfully!")

def base64_to_pil(base64_str: str) -> Image.Image:
    """将base64字符串转换为PIL Image对象"""
    try:
        # 移除可能的 data:image/xxx;base64, 前缀
        if ',' in base64_str:
            base64_str = base64_str.split(',', 1)[1]

        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        return image
    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {str(e)}")

@app.post("/ocr/batch", response_model=OCRBatchResponse)
async def ocr_batch_endpoint(request: OCRRequest):
    """
    批量OCR识别接口
    接收多张base64编码的图片，返回每张图片的识别结果
    """
    try:
        logger.info(f"Received batch OCR request, mode: {request.mode}, images count: {len(request.images)}")

        if not request.images:
            raise HTTPException(status_code=400, detail="images list cannot be empty")

        # 确定使用的 prompt
        if request.custom_prompt:
            prompt = request.custom_prompt
            logger.info(f"Using custom prompt: {prompt[:50]}...")
        else:
            prompt = MODE_PROMPTS[request.mode]
            # 如果是 locate_object 模式，需要填充 reference
            if request.mode == OCRMode.LOCATE_OBJECT:
                if not request.reference:
                    raise HTTPException(
                        status_code=400,
                        detail="reference parameter is required for locate_object mode"
                    )
                prompt = prompt.format(reference=request.reference)
            logger.info(f"Using mode '{request.mode}' with prompt: {prompt[:50]}...")

        # 解码所有图片
        pil_images = []
        for i, base64_img in enumerate(request.images):
            try:
                pil_image = base64_to_pil(base64_img)
                pil_images.append(pil_image)
                logger.info(f"Image {i+1}/{len(request.images)} loaded: {pil_image.size}")
            except Exception as e:
                logger.error(f"Failed to load image {i+1}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to load image {i+1}: {str(e)}"
                )

        # 准备批量输入
        model_inputs = []
        for pil_image in pil_images:
            model_inputs.append({
                "prompt": prompt,
                "multi_modal_data": {"image": pil_image}
            })

        # 采样参数
        sampling_param = SamplingParams(
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            extra_args=dict(
                ngram_size=30,
                window_size=90,
                whitelist_token_ids={128821, 128822},  # whitelist: <td>, </td>
            ),
            skip_special_tokens=False,
        )

        # 批量生成
        logger.info(f"Generating OCR results for {len(model_inputs)} images...")
        outputs = llm.generate(model_inputs, sampling_param)

        # 构建响应
        results = []
        success_count = 0
        for i, output in enumerate(outputs):
            result_text = output.outputs[0].text
            logger.info(f"OCR completed for image {i+1}, result length: {len(result_text)}")

            results.append(OCRResult(
                result=result_text,
                mode=request.mode,
                prompt=prompt,
                image_size=list(pil_images[i].size)
            ))
            success_count += 1

        logger.info(f"Batch OCR completed: {success_count}/{len(request.images)} succeeded")

        return OCRBatchResponse(
            results=results,
            total=len(request.images),
            success_count=success_count,
            failed_count=len(request.images) - success_count
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch OCR error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ocr")
async def ocr_single_endpoint(request: OCRRequest):
    """
    单张图片OCR识别接口（兼容性接口）
    如果传入多张图片，只处理第一张
    """
    try:
        if not request.images:
            raise HTTPException(status_code=400, detail="images list cannot be empty")

        logger.info(f"Received single OCR request, mode: {request.mode}")

        # 只处理第一张图片
        single_request = OCRRequest(
            images=[request.images[0]],
            mode=request.mode,
            custom_prompt=request.custom_prompt,
            reference=request.reference,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        batch_response = await ocr_batch_endpoint(single_request)

        if batch_response.results:
            result = batch_response.results[0]
            return JSONResponse(content={
                "result": result.result,
                "mode": result.mode,
                "prompt": result.prompt,
                "image_size": result.image_size
            })
        else:
            raise HTTPException(status_code=500, detail="OCR processing failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single OCR error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "/mnt/models/DeepSeek-OCR",
        "version": "2.0.0",
        "backend": "vLLM",
        "features": ["batch_processing", "base64_input"]
    }

@app.get("/modes")
async def list_modes():
    """列出所有支持的 OCR 模式"""
    return {
        "modes": [
            {
                "mode": OCRMode.FREE_OCR,
                "description": "Basic OCR without formatting",
                "prompt": MODE_PROMPTS[OCRMode.FREE_OCR]
            },
            {
                "mode": OCRMode.CONVERT_TO_MARKDOWN,
                "description": "Convert document to markdown (default)",
                "prompt": MODE_PROMPTS[OCRMode.CONVERT_TO_MARKDOWN]
            },
            {
                "mode": OCRMode.PARSE_FIGURE,
                "description": "Parse figures and charts",
                "prompt": MODE_PROMPTS[OCRMode.PARSE_FIGURE]
            },
            {
                "mode": OCRMode.LOCATE_OBJECT,
                "description": "Locate objects by reference text",
                "prompt": MODE_PROMPTS[OCRMode.LOCATE_OBJECT],
                "requires": "reference parameter"
            }
        ]
    }

@app.get("/")
async def root():
    return {
        "message": "DeepSeek-OCR API with Batch Base64 Support",
        "version": "2.0.0",
        "endpoints": {
            "POST /ocr": "Single image OCR (base64)",
            "POST /ocr/batch": "Batch images OCR (base64)",
            "GET /health": "Health check",
            "GET /modes": "List all OCR modes",
            "GET /": "API info",
            "GET /docs": "API documentation (Swagger UI)"
        },
        "usage_examples": {
            "batch_markdown": {
                "method": "POST",
                "url": "/ocr/batch",
                "body": {
                    "images": ["base64_image_1", "base64_image_2"],
                    "mode": "convert_to_markdown",
                    "max_tokens": 8192,
                    "temperature": 0.0
                }
            },
            "single_markdown": {
                "method": "POST",
                "url": "/ocr",
                "body": {
                    "images": ["base64_image"],
                    "mode": "convert_to_markdown"
                }
            }
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9123,
        log_level="info",
        timeout_keep_alive=300
    )
