"""
ComfyUI 图片生成客户端
支持远程 ComfyUI 服务器通信

工作原理:
1. 加载工作流模板 (JSON)
2. 动态修改参数 (prompt, seed, 尺寸等)
3. 通过 WebSocket 提交任务并监听进度
4. 从 ComfyUI 服务器下载生成的图片
"""
import json
import uuid
import asyncio
import logging
import httpx
import websockets
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

from app.api.settings import get_comfyui_config

logger = logging.getLogger(__name__)

# 默认工作流目录
WORKFLOWS_DIR = Path(__file__).parent.parent.parent / "workflows"


class ComfyUIClient:
    """ComfyUI 客户端"""
    
    def __init__(self, api_url: Optional[str] = None):
        """
        初始化 ComfyUI 客户端
        
        Args:
            api_url: ComfyUI API 地址，如 http://192.168.1.106:8188
        """
        if api_url:
            self.api_url = api_url.rstrip('/')
        else:
            config = get_comfyui_config()
            self.api_url = config.api_url.rstrip('/')
        
        # WebSocket URL
        self.ws_url = self.api_url.replace('http://', 'ws://').replace('https://', 'wss://')
        self.client_id = str(uuid.uuid4())
    
    async def check_connection(self) -> Dict[str, Any]:
        """
        检查 ComfyUI 服务器连接状态
        
        Returns:
            服务器系统信息
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/system_stats")
                if response.status_code == 200:
                    return {"success": True, "stats": response.json()}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/queue")
                return response.json()
        except Exception as e:
            logger.error(f"获取队列状态失败: {e}")
            return {}
    
    async def get_history(self, prompt_id: str) -> Dict[str, Any]:
        """获取任务历史"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.api_url}/history/{prompt_id}")
                return response.json()
        except Exception as e:
            logger.error(f"获取历史失败: {e}")
            return {}
    
    def load_workflow(self, workflow_path: Optional[str] = None) -> Dict[str, Any]:
        """
        加载工作流模板
        
        Args:
            workflow_path: 工作流文件名或路径，为 None 时使用默认工作流
            
        Returns:
            工作流字典
        """
        if workflow_path:
            # 支持只传文件名（如 "Multi-LoRA-SD1.json"）或完整路径
            path = Path(workflow_path)
            if not path.is_absolute():
                path = WORKFLOWS_DIR / workflow_path
        else:
            # 使用默认工作流
            path = WORKFLOWS_DIR / "simple.json"
        
        if not path.exists():
            raise FileNotFoundError(f"工作流文件不存在: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _find_node_by_class(self, workflow: Dict[str, Any], class_type: str) -> Optional[str]:
        """
        根据 class_type 查找节点ID
        
        Args:
            workflow: 工作流字典
            class_type: 节点类型名称
            
        Returns:
            节点ID 或 None
        """
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and node_data.get("class_type") == class_type:
                return node_id
        return None
    
    def _find_positive_prompt_node(self, workflow: Dict[str, Any]) -> Optional[str]:
        """
        查找正面提示词节点（连接到 KSampler 的 positive 输入）
        """
        # 先找 KSampler
        ksampler_id = self._find_node_by_class(workflow, "KSampler")
        if ksampler_id and "positive" in workflow[ksampler_id].get("inputs", {}):
            positive_link = workflow[ksampler_id]["inputs"]["positive"]
            if isinstance(positive_link, list) and len(positive_link) >= 1:
                return str(positive_link[0])
        return None
    
    def _find_negative_prompt_node(self, workflow: Dict[str, Any]) -> Optional[str]:
        """
        查找负面提示词节点（连接到 KSampler 的 negative 输入）
        """
        ksampler_id = self._find_node_by_class(workflow, "KSampler")
        if ksampler_id and "negative" in workflow[ksampler_id].get("inputs", {}):
            negative_link = workflow[ksampler_id]["inputs"]["negative"]
            if isinstance(negative_link, list) and len(negative_link) >= 1:
                return str(negative_link[0])
        return None
    
    def modify_workflow(
        self,
        workflow: Dict[str, Any],
        prompt: str,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 7.0,
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """
        修改工作流参数（智能识别不同工作流结构）
        
        自动查找以下节点类型:
        - CLIPTextEncode: 正面/负面提示词
        - KSampler: seed, steps, cfg
        - EmptyLatentImage: width, height, batch_size
        
        Args:
            workflow: 工作流字典
            prompt: 正面提示词
            negative_prompt: 负面提示词
            seed: 随机种子
            width: 图片宽度
            height: 图片高度
            steps: 采样步数
            cfg_scale: CFG Scale
            batch_size: 批量大小
            
        Returns:
            修改后的工作流
        """
        # 深拷贝避免修改原始工作流
        workflow = json.loads(json.dumps(workflow))
        
        # 智能查找正面提示词节点
        positive_node = self._find_positive_prompt_node(workflow)
        if positive_node and positive_node in workflow:
            workflow[positive_node]["inputs"]["text"] = prompt
            logger.debug(f"设置正面提示词到节点 {positive_node}")
        
        # 智能查找负面提示词节点
        if negative_prompt:
            negative_node = self._find_negative_prompt_node(workflow)
            if negative_node and negative_node in workflow:
                workflow[negative_node]["inputs"]["text"] = negative_prompt
                logger.debug(f"设置负面提示词到节点 {negative_node}")
        
        # 查找并修改 KSampler 参数
        ksampler_id = self._find_node_by_class(workflow, "KSampler")
        if ksampler_id:
            if seed is not None:
                workflow[ksampler_id]["inputs"]["seed"] = seed
            workflow[ksampler_id]["inputs"]["steps"] = steps
            workflow[ksampler_id]["inputs"]["cfg"] = cfg_scale
            logger.debug(f"设置 KSampler 参数到节点 {ksampler_id}")
        
        # 查找并修改图片尺寸
        latent_id = self._find_node_by_class(workflow, "EmptyLatentImage")
        if latent_id:
            workflow[latent_id]["inputs"]["width"] = width
            workflow[latent_id]["inputs"]["height"] = height
            workflow[latent_id]["inputs"]["batch_size"] = batch_size
            logger.debug(f"设置图片尺寸到节点 {latent_id}: {width}x{height}")
        
        return workflow
    
    async def queue_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交工作流到队列
        
        Args:
            workflow: 工作流字典
            
        Returns:
            包含 prompt_id 的响应
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/prompt",
                    json=payload
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_text = response.text
                    logger.error(f"提交工作流失败: HTTP {response.status_code} - {error_text[:500]}")
                    return {"error": f"HTTP {response.status_code}: {error_text[:200]}"}
                    
        except Exception as e:
            logger.exception(f"提交工作流失败: {e}")
            return {"error": str(e)}
    
    async def wait_for_completion(
        self, 
        prompt_id: str, 
        timeout: float = 300.0,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        使用 WebSocket 等待任务完成
        
        Args:
            prompt_id: 任务 ID
            timeout: 超时时间（秒）
            progress_callback: 进度回调函数 (progress: float, status: str)
            
        Returns:
            任务结果
        """
        ws_url = f"{self.ws_url}/ws?clientId={self.client_id}"
        
        try:
            async with websockets.connect(ws_url, close_timeout=10) as websocket:
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    # 检查超时
                    elapsed = asyncio.get_event_loop().time() - start_time
                    if elapsed > timeout:
                        return {"error": "生成超时"}
                    
                    try:
                        # 设置接收超时
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=10.0
                        )
                        
                        # 跳过二进制消息（如预览图片）
                        if isinstance(message, bytes):
                            logger.debug("收到二进制消息（预览图片），跳过")
                            continue
                        
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "progress":
                            # 进度更新
                            progress_data = data.get("data", {})
                            value = progress_data.get("value", 0)
                            max_val = progress_data.get("max", 1)
                            progress = (value / max_val) * 100 if max_val > 0 else 0
                            
                            if progress_callback:
                                await progress_callback(progress, "generating")
                            
                            logger.debug(f"生成进度: {progress:.1f}%")
                        
                        elif msg_type == "executing":
                            # 正在执行
                            exec_data = data.get("data", {})
                            if exec_data.get("prompt_id") == prompt_id:
                                node = exec_data.get("node")
                                if node is None:
                                    # 执行完成
                                    logger.info(f"任务 {prompt_id} 执行完成")
                                    return {"success": True, "prompt_id": prompt_id}
                        
                        elif msg_type == "executed":
                            # 节点执行完成
                            exec_data = data.get("data", {})
                            if exec_data.get("prompt_id") == prompt_id:
                                logger.debug(f"节点执行完成: {exec_data.get('node')}")
                        
                        elif msg_type == "execution_error":
                            # 执行错误
                            error_data = data.get("data", {})
                            if error_data.get("prompt_id") == prompt_id:
                                error_msg = error_data.get("exception_message", "未知错误")
                                logger.error(f"执行错误: {error_msg}")
                                return {"error": error_msg}
                    
                    except asyncio.TimeoutError:
                        # WebSocket 接收超时，检查历史记录
                        history = await self.get_history(prompt_id)
                        if prompt_id in history:
                            return {"success": True, "prompt_id": prompt_id}
                        continue
                        
        except Exception as e:
            logger.exception(f"WebSocket 连接失败: {e}")
            # 回退到轮询方式
            return await self._poll_for_completion(prompt_id, timeout)
    
    async def _poll_for_completion(
        self, 
        prompt_id: str, 
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        使用轮询方式等待任务完成（WebSocket 失败时的回退方案）
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {"error": "生成超时"}
            
            history = await self.get_history(prompt_id)
            
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                status = history[prompt_id].get("status", {})
                
                if status.get("status_str") == "error":
                    return {"error": status.get("messages", ["未知错误"])}
                
                return {"success": True, "prompt_id": prompt_id, "outputs": outputs}
            
            await asyncio.sleep(1)
    
    async def get_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output"
    ) -> bytes:
        """
        从 ComfyUI 服务器下载图片
        
        Args:
            filename: 图片文件名
            subfolder: 子目录
            folder_type: 目录类型 (output, input, temp)
            
        Returns:
            图片二进制数据
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self.api_url}/view",
                params=params
            )
            response.raise_for_status()
            return response.content
    
    async def generate_image(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 3.5,
        workflow_path: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        生成图片的完整流程
        
        Args:
            prompt: 正面提示词
            output_path: 输出路径
            negative_prompt: 负面提示词
            seed: 随机种子
            width: 图片宽度
            height: 图片高度
            steps: 采样步数
            cfg_scale: CFG Scale
            workflow_path: 工作流路径
            progress_callback: 进度回调
            
        Returns:
            生成结果
        """
        try:
            # 1. 加载工作流
            workflow = self.load_workflow(workflow_path)
            logger.info(f"已加载工作流: {workflow_path or 'default'}")
            
            # 2. 生成种子
            if seed is None:
                seed = uuid.uuid4().int % (2**32)
            
            # 3. 修改工作流参数
            workflow = self.modify_workflow(
                workflow=workflow,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                width=width,
                height=height,
                steps=steps,
                cfg_scale=cfg_scale
            )
            
            logger.info(f"ComfyUI 生成参数: seed={seed}, size={width}x{height}, steps={steps}")
            
            # 4. 提交到队列
            result = await self.queue_prompt(workflow)
            
            if "error" in result:
                return {"success": False, "error": result["error"]}
            
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                return {"success": False, "error": "未获取到 prompt_id"}
            
            logger.info(f"任务已提交: {prompt_id}")
            
            # 5. 等待完成
            completion = await self.wait_for_completion(
                prompt_id, 
                timeout=300.0,
                progress_callback=progress_callback
            )
            
            if "error" in completion:
                return {"success": False, "error": completion["error"]}
            
            # 6. 获取输出图片
            history = await self.get_history(prompt_id)
            
            if prompt_id not in history:
                return {"success": False, "error": "未找到任务结果"}
            
            outputs = history[prompt_id].get("outputs", {})
            
            # 查找 SaveImage 节点的输出 (节点 12)
            images = []
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    images.extend(node_output["images"])
            
            if not images:
                return {"success": False, "error": "未生成任何图片"}
            
            # 7. 下载第一张图片
            image_info = images[0]
            image_data = await self.get_image(
                filename=image_info["filename"],
                subfolder=image_info.get("subfolder", ""),
                folder_type=image_info.get("type", "output")
            )
            
            # 8. 保存到本地
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"图片已保存: {output_path}")
            
            return {
                "success": True,
                "path": str(output_path),
                "seed": seed,
                "prompt": prompt,
                "width": width,
                "height": height,
                "prompt_id": prompt_id,
                "comfyui_filename": image_info["filename"]
            }
            
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception(f"ComfyUI 生成失败: {e}")
            return {"success": False, "error": str(e)}


# 便捷函数
async def generate_image_comfyui(
    prompt: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg_scale: float = 3.5,
    workflow_path: Optional[str] = None,
    api_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用 ComfyUI 生成图片的便捷函数
    
    Args:
        prompt: 正面提示词
        output_path: 输出路径
        negative_prompt: 负面提示词  
        seed: 随机种子
        width: 图片宽度
        height: 图片高度
        steps: 采样步数
        cfg_scale: CFG Scale
        workflow_path: 工作流路径
        api_url: ComfyUI API 地址
        
    Returns:
        生成结果
    """
    client = ComfyUIClient(api_url)
    return await client.generate_image(
        prompt=prompt,
        output_path=output_path,
        negative_prompt=negative_prompt,
        seed=seed,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        workflow_path=workflow_path
    )
