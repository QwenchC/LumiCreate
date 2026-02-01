<template>
  <div class="config-panel">
    <!-- AI 助填区域 -->
    <div class="ai-fill-section">
      <el-input
        v-model="aiFillInput"
        type="textarea"
        :rows="2"
        placeholder="用自然语言描述你想要的配置，例如：我想做玄幻爽文风，下饭解说，男主从底层逆袭，20分钟左右，节奏快，画面偏国风暗黑"
        class="ai-fill-input"
      />
      <el-button 
        type="primary" 
        @click="handleAiFill"
        :loading="aiFilling"
        class="ai-fill-btn"
      >
        <el-icon><MagicStick /></el-icon>
        AI 助填
      </el-button>
    </div>
    
    <!-- 配置表单 -->
    <el-form :model="localConfig" label-width="130px" class="config-form">
      
      <!-- ========== 文案生成配置 ========== -->
      <el-collapse v-model="activeCollapse">
        <el-collapse-item title="文案生成配置" name="script_generation">
          <template #title>
            <span class="collapse-title">
              <el-icon><Document /></el-icon>
              文案生成配置
            </span>
          </template>
          
          <!-- 基础设定 -->
          <div class="config-subsection">
            <h4>基础设定</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="题材/类型">
                  <el-select v-model="localConfig.script_generation.genre" placeholder="选择题材" clearable>
                    <el-option label="玄幻" value="玄幻" />
                    <el-option label="武侠" value="武侠" />
                    <el-option label="都市" value="都市" />
                    <el-option label="悬疑" value="悬疑" />
                    <el-option label="历史" value="历史" />
                    <el-option label="科幻" value="科幻" />
                    <el-option label="恐怖" value="恐怖" />
                    <el-option label="轻松搞笑" value="轻松搞笑" />
                    <el-option label="言情" value="言情" />
                    <el-option label="游戏" value="游戏" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="受众口味">
                  <el-select v-model="localConfig.script_generation.audience_taste" placeholder="选择口味" clearable>
                    <el-option label="下饭" value="下饭" />
                    <el-option label="爽文" value="爽文" />
                    <el-option label="推理烧脑" value="推理烧脑" />
                    <el-option label="治愈" value="治愈" />
                    <el-option label="热血" value="热血" />
                    <el-option label="虐心" value="虐心" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="叙事视角">
                  <el-select v-model="localConfig.script_generation.narrative_perspective" placeholder="选择视角" clearable>
                    <el-option label="第一人称" value="第一人称" />
                    <el-option label="第三人称" value="第三人称" />
                    <el-option label="旁白式" value="旁白式" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="文风">
                  <el-select v-model="localConfig.script_generation.writing_style" placeholder="选择文风" clearable>
                    <el-option label="口语" value="口语" />
                    <el-option label="文艺" value="文艺" />
                    <el-option label="古风" value="古风" />
                    <el-option label="网文" value="网文" />
                    <el-option label="冷幽默" value="冷幽默" />
                    <el-option label="严肃纪实" value="严肃纪实" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="节奏">
                  <el-select v-model="localConfig.script_generation.pacing" placeholder="选择节奏" clearable>
                    <el-option label="慢热" value="慢热" />
                    <el-option label="中速" value="中速" />
                    <el-option label="快节奏" value="快节奏" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="高潮位置">
                  <el-select v-model="localConfig.script_generation.climax_position" placeholder="选择位置" clearable>
                    <el-option label="开头" value="开头" />
                    <el-option label="中段" value="中段" />
                    <el-option label="结尾" value="结尾" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 主线设定 -->
          <div class="config-subsection">
            <h4>主线设定</h4>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="世界观关键词">
                  <el-input v-model="localConfig.script_generation.world_setting" placeholder="如：修真世界、末日废土" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="金手指/主角优势">
                  <el-input v-model="localConfig.script_generation.golden_finger" placeholder="如：系统、重生记忆、透视眼" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="矛盾冲突类型">
                  <el-input v-model="localConfig.script_generation.conflict_type" placeholder="如：阶级对立、复仇、夺宝" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="反转频率">
                  <el-select v-model="localConfig.script_generation.twist_frequency" placeholder="选择频率" clearable>
                    <el-option label="低" value="低" />
                    <el-option label="中" value="中" />
                    <el-option label="高" value="高" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 角色设定 -->
          <div class="config-subsection">
            <h4>主角设定</h4>
            <el-row :gutter="20">
              <el-col :span="6">
                <el-form-item label="姓名">
                  <el-input v-model="localConfig.script_generation.protagonist.name" placeholder="主角姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="性别">
                  <el-select v-model="localConfig.script_generation.protagonist.gender" placeholder="选择性别" clearable>
                    <el-option label="男" value="男" />
                    <el-option label="女" value="女" />
                    <el-option label="未知" value="未知" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="年龄/年龄段">
                  <el-input v-model="localConfig.script_generation.protagonist.age" placeholder="如：18岁、中年" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="配角数量">
                  <el-input-number v-model="localConfig.script_generation.supporting_characters_count" :min="0" :max="10" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="性格特点">
                  <el-input v-model="localConfig.script_generation.protagonist.personality" placeholder="如：隐忍、腹黑、热血" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="背景故事">
                  <el-input v-model="localConfig.script_generation.protagonist.background" placeholder="如：落魄富家子、废材逆袭" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 长度目标 -->
          <div class="config-subsection">
            <h4>长度目标</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="总字数目标">
                  <el-input-number v-model="localConfig.script_generation.target_word_count" :min="500" :max="50000" :step="500" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="总时长(分钟)">
                  <el-input-number v-model="localConfig.script_generation.target_duration_minutes" :min="1" :max="60" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="每段目标字数">
                  <el-input-number v-model="localConfig.script_generation.segment_word_count" :min="50" :max="2000" :step="50" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 合规设置 -->
          <div class="config-subsection">
            <h4>合规设置</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="避免血腥暴力">
                  <el-switch v-model="localConfig.script_generation.no_violence" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="避免成人内容">
                  <el-switch v-model="localConfig.script_generation.no_adult_content" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="避免敏感话题">
                  <el-switch v-model="localConfig.script_generation.no_sensitive_topics" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 高级设置 -->
          <div class="config-subsection">
            <h4>高级设置</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="生成画面描述">
                  <el-switch v-model="localConfig.script_generation.require_visual_prompts" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="生成段落标题">
                  <el-switch v-model="localConfig.script_generation.require_segment_titles" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="系统提示词模板">
                  <el-input 
                    v-model="localConfig.script_generation.system_prompt_template" 
                    type="textarea" 
                    :rows="3"
                    placeholder="自定义系统提示词（留空使用默认）"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </el-collapse-item>
        
        <!-- ========== 切分配置 ========== -->
        <el-collapse-item title="切分配置" name="segmenter">
          <template #title>
            <span class="collapse-title">
              <el-icon><Scissor /></el-icon>
              切分配置
            </span>
          </template>
          
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="切分策略">
                <el-select v-model="localConfig.segmenter.strategy" placeholder="选择策略">
                  <el-option label="按字数阈值" value="按字数阈值" />
                  <el-option label="按语义" value="按语义" />
                  <el-option label="按镜头脚本" value="按镜头脚本" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="最小段落字数">
                <el-input-number v-model="localConfig.segmenter.min_segment_length" :min="20" :max="500" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="最大段落字数">
                <el-input-number v-model="localConfig.segmenter.max_segment_length" :min="100" :max="2000" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="6">
              <el-form-item label="必须包含旁白">
                <el-switch v-model="localConfig.segmenter.require_narration" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="必须包含画面提示词">
                <el-switch v-model="localConfig.segmenter.require_visual_prompt" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="包含氛围标签">
                <el-switch v-model="localConfig.segmenter.require_mood" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="包含镜头类型">
                <el-switch v-model="localConfig.segmenter.require_shot_type" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-collapse-item>
        
        <!-- ========== 出图配置 ========== -->
        <el-collapse-item title="出图配置" name="image_generation">
          <template #title>
            <span class="collapse-title">
              <el-icon><Picture /></el-icon>
              出图配置
            </span>
          </template>
          
          <!-- 生图引擎选择 -->
          <div class="config-subsection">
            <h4>生图引擎</h4>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="引擎选择">
                  <el-radio-group v-model="localConfig.image_generation.engine">
                    <el-radio value="pollinations">
                      <span class="engine-option">
                        <strong>Pollinations.ai</strong>
                        <el-tag size="small" type="success">推荐</el-tag>
                      </span>
                      <div class="engine-desc">云端生图，无需GPU，速度快</div>
                    </el-radio>
                    <el-radio value="comfyui">
                      <span class="engine-option">
                        <strong>ComfyUI</strong>
                      </span>
                      <div class="engine-desc">本地生图，需要GPU，可自定义工作流</div>
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="12" v-if="localConfig.image_generation.engine === 'pollinations'">
                <el-form-item label="Pollinations 模型">
                  <el-select v-model="localConfig.image_generation.pollinations_model" placeholder="选择模型">
                    <el-option label="Flux (默认)" value="flux" />
                    <el-option label="Turbo (快速)" value="turbo" />
                    <el-option label="Flux Realism (写实)" value="flux-realism" />
                    <el-option label="Flux Anime (动漫)" value="flux-anime" />
                    <el-option label="Flux 3D" value="flux-3d" />
                    <el-option label="Any Dark (暗黑)" value="any-dark" />
                    <el-option label="Flux Pro (高质量)" value="flux-pro" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 画风设置（通用） -->
          <div class="config-subsection">
            <h4>画风设置 <el-tag size="small" type="info">对所有引擎生效</el-tag></h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="画风">
                  <el-select v-model="localConfig.image_generation.style" placeholder="选择画风">
                    <el-option label="国风" value="国风" />
                    <el-option label="赛博" value="赛博" />
                    <el-option label="写实" value="写实" />
                    <el-option label="动漫" value="动漫" />
                    <el-option label="暗黑" value="暗黑" />
                    <el-option label="油画" value="油画" />
                    <el-option label="水彩" value="水彩" />
                    <el-option label="极简" value="极简" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="分辨率">
                  <el-select v-model="localConfig.image_generation.resolution" placeholder="选择分辨率">
                    <el-option label="512" value="512" />
                    <el-option label="768" value="768" />
                    <el-option label="1024" value="1024" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="画面比例">
                  <el-select v-model="localConfig.image_generation.aspect_ratio" placeholder="选择比例">
                    <el-option label="横屏16:9" value="横屏16:9" />
                    <el-option label="竖屏9:16" value="竖屏9:16" />
                    <el-option label="正方形1:1" value="正方形1:1" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- ComfyUI 特有参数 -->
          <div class="config-subsection" v-if="localConfig.image_generation.engine === 'comfyui'">
            <h4>ComfyUI 采样参数</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="采样步数">
                  <el-input-number v-model="localConfig.image_generation.steps" :min="1" :max="100" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="CFG Scale">
                  <el-slider v-model="localConfig.image_generation.cfg_scale" :min="1" :max="20" :step="0.5" show-input />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="采样器">
                  <el-select v-model="localConfig.image_generation.sampler" placeholder="选择采样器">
                    <el-option label="Euler Ancestral" value="euler_ancestral" />
                    <el-option label="Euler" value="euler" />
                    <el-option label="DPM++ 2M" value="dpmpp_2m" />
                    <el-option label="DPM++ SDE" value="dpmpp_sde" />
                    <el-option label="DDIM" value="ddim" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="随机种子">
                  <el-input-number v-model="localConfig.image_generation.seed" :min="0" placeholder="留空随机" />
                </el-form-item>
              </el-col>
              <el-col :span="16">
                <el-form-item label="负面提示词">
                  <el-input v-model="localConfig.image_generation.negative_prompt" placeholder="low quality, blurry, watermark..." />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 批量生成 -->
          <div class="config-subsection">
            <h4>批量生成</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="每段候选图数">
                  <el-input-number v-model="localConfig.image_generation.candidates_per_segment" :min="1" :max="10" />
                </el-form-item>
              </el-col>
              <el-col :span="8" v-if="localConfig.image_generation.engine === 'comfyui'">
                <el-form-item label="并行生成">
                  <el-switch v-model="localConfig.image_generation.parallel_generation" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="最大重试次数">
                  <el-input-number v-model="localConfig.image_generation.max_retries" :min="0" :max="10" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- ComfyUI 工作流设置 -->
          <div class="config-subsection" v-if="localConfig.image_generation.engine === 'comfyui'">
            <h4>工作流设置</h4>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="工作流ID">
                  <el-input v-model="localConfig.image_generation.workflow_id" placeholder="ComfyUI工作流ID" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="备用工作流ID">
                  <el-input v-model="localConfig.image_generation.fallback_workflow_id" placeholder="失败时使用的备用工作流" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="角色LoRA ID">
                  <el-input v-model="localConfig.image_generation.character_lora_id" placeholder="主体一致性LoRA（预留）" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="参考图ID">
                  <el-input v-model="localConfig.image_generation.reference_image_id" placeholder="参考图资产ID（预留）" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </el-collapse-item>
        
        <!-- ========== 语音配置 ========== -->
        <el-collapse-item title="语音配置" name="tts">
          <template #title>
            <span class="collapse-title">
              <el-icon><Microphone /></el-icon>
              语音配置
            </span>
          </template>
          
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="TTS引擎">
                <el-select v-model="localConfig.tts.engine" placeholder="选择引擎">
                  <el-option label="Edge TTS (免费)" value="free_tts" />
                  <el-option label="GPT-SoVITS" value="gpt_sovits" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="音色类型">
                <el-select v-model="localConfig.tts.voice_type" placeholder="选择音色">
                  <el-option label="男-青年" value="男-青年" />
                  <el-option label="男-中年" value="男-中年" />
                  <el-option label="男-老年" value="男-老年" />
                  <el-option label="女-青年" value="女-青年" />
                  <el-option label="女-中年" value="女-中年" />
                  <el-option label="女-老年" value="女-老年" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="输出格式">
                <el-select v-model="localConfig.tts.output_format" placeholder="选择格式">
                  <el-option label="MP3" value="mp3" />
                  <el-option label="WAV" value="wav" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="语速">
                <el-slider v-model="localConfig.tts.speed" :min="0.5" :max="2" :step="0.1" show-input />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="音量">
                <el-slider v-model="localConfig.tts.volume" :min="0.1" :max="2" :step="0.1" show-input />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="音调">
                <el-slider v-model="localConfig.tts.pitch" :min="0.5" :max="2" :step="0.1" show-input />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="句间停顿(秒)">
                <el-slider v-model="localConfig.tts.pause_between_sentences" :min="0" :max="2" :step="0.1" show-input />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="自定义音色ID">
                <el-input v-model="localConfig.tts.custom_voice_id" placeholder="GPT-SoVITS自定义音色" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="情绪标签">
                <el-input v-model="localConfig.tts.emotion" placeholder="预留功能" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-collapse-item>
        
        <!-- ========== 视频合成配置 ========== -->
        <el-collapse-item title="视频合成配置" name="video_composer">
          <template #title>
            <span class="collapse-title">
              <el-icon><VideoCamera /></el-icon>
              视频合成配置
            </span>
          </template>
          
          <!-- 基础参数 -->
          <div class="config-subsection">
            <h4>基础参数</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="帧率">
                  <el-select v-model="localConfig.video_composer.frame_rate" placeholder="选择帧率">
                    <el-option label="24 fps" value="24" />
                    <el-option label="30 fps" value="30" />
                    <el-option label="60 fps" value="60" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="分辨率">
                  <el-select v-model="localConfig.video_composer.resolution" placeholder="选择分辨率">
                    <el-option label="720p" value="720p" />
                    <el-option label="1080p" value="1080p" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="竖屏模式">
                  <el-switch v-model="localConfig.video_composer.is_portrait" />
                  <span class="form-tip">{{ localConfig.video_composer.is_portrait ? '1080x1920' : '1920x1080' }}</span>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 转场设置 -->
          <div class="config-subsection">
            <h4>转场设置</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="转场类型">
                  <el-select v-model="localConfig.video_composer.transition_type" placeholder="选择转场">
                    <el-option label="淡入淡出" value="淡入淡出" />
                    <el-option label="硬切" value="硬切" />
                    <el-option label="推拉" value="推拉" />
                    <el-option label="缩放" value="缩放" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="转场时长(秒)">
                  <el-slider v-model="localConfig.video_composer.transition_duration" :min="0" :max="2" :step="0.1" show-input />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 背景音乐 -->
          <div class="config-subsection">
            <h4>背景音乐</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="启用BGM">
                  <el-switch v-model="localConfig.video_composer.bgm_enabled" />
                </el-form-item>
              </el-col>
              <el-col :span="8" v-if="localConfig.video_composer.bgm_enabled">
                <el-form-item label="BGM音量">
                  <el-slider v-model="localConfig.video_composer.bgm_volume" :min="0" :max="1" :step="0.05" show-input />
                </el-form-item>
              </el-col>
              <el-col :span="8" v-if="localConfig.video_composer.bgm_enabled">
                <el-form-item label="语音时降低BGM">
                  <el-switch v-model="localConfig.video_composer.bgm_ducking" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20" v-if="localConfig.video_composer.bgm_enabled">
              <el-col :span="12">
                <el-form-item label="BGM资产ID">
                  <el-input-number v-model="localConfig.video_composer.bgm_asset_id" :min="0" placeholder="背景音乐资产ID" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 字幕设置 -->
          <div class="config-subsection">
            <h4>字幕设置</h4>
            <el-row :gutter="20">
              <el-col :span="6">
                <el-form-item label="启用字幕">
                  <el-switch v-model="localConfig.video_composer.subtitle_enabled" />
                </el-form-item>
              </el-col>
              <el-col :span="6" v-if="localConfig.video_composer.subtitle_enabled">
                <el-form-item label="字幕格式">
                  <el-select v-model="localConfig.video_composer.subtitle_format" placeholder="选择格式">
                    <el-option label="SRT" value="srt" />
                    <el-option label="ASS" value="ass" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6" v-if="localConfig.video_composer.subtitle_enabled">
                <el-form-item label="字幕位置">
                  <el-select v-model="localConfig.video_composer.subtitle_position" placeholder="选择位置">
                    <el-option label="底部" value="底部" />
                    <el-option label="顶部" value="顶部" />
                    <el-option label="居中" value="居中" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6" v-if="localConfig.video_composer.subtitle_enabled">
                <el-form-item label="字幕描边">
                  <el-switch v-model="localConfig.video_composer.subtitle_outline" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20" v-if="localConfig.video_composer.subtitle_enabled">
              <el-col :span="8">
                <el-form-item label="字幕字体">
                  <el-input v-model="localConfig.video_composer.subtitle_font" placeholder="Microsoft YaHei" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="字号">
                  <el-input-number v-model="localConfig.video_composer.subtitle_font_size" :min="12" :max="120" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="字幕颜色">
                  <el-color-picker v-model="localConfig.video_composer.subtitle_color" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 水印设置 -->
          <div class="config-subsection">
            <h4>水印设置</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="启用水印">
                  <el-switch v-model="localConfig.video_composer.watermark_enabled" />
                </el-form-item>
              </el-col>
              <el-col :span="16" v-if="localConfig.video_composer.watermark_enabled">
                <el-form-item label="水印文字">
                  <el-input v-model="localConfig.video_composer.watermark_text" placeholder="水印内容" />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
          
          <!-- 时长计算 -->
          <div class="config-subsection">
            <h4>时长计算</h4>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="最小段落时长(秒)">
                  <el-slider v-model="localConfig.video_composer.min_segment_duration" :min="0.5" :max="10" :step="0.5" show-input />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="段落时长补充(秒)">
                  <el-slider v-model="localConfig.video_composer.segment_padding" :min="0" :max="2" :step="0.1" show-input />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="字数/秒估算">
                  <el-slider v-model="localConfig.video_composer.fallback_chars_per_second" :min="1" :max="10" :step="0.5" show-input />
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </el-collapse-item>
      </el-collapse>
      
      <!-- 保存按钮 -->
      <div class="form-actions">
        <el-button type="primary" @click="handleSave" :loading="saving">
          <el-icon><Check /></el-icon>
          保存配置
        </el-button>
        <el-button @click="handleReset">
          <el-icon><RefreshLeft /></el-icon>
          重置默认
        </el-button>
      </div>
    </el-form>
    
    <!-- AI 助填结果对话框 -->
    <el-dialog v-model="showAiFillResult" title="AI 助填结果" width="800px">
      <div class="ai-fill-result">
        <p class="result-hint">
          <el-icon><InfoFilled /></el-icon>
          AI 根据您的描述推荐了以下配置，确认后将自动填入：
        </p>
        <div v-if="aiFillExplanation" class="result-explanation">
          <strong>AI 解释：</strong>{{ aiFillExplanation }}
        </div>
        <div class="result-preview">
          <pre>{{ JSON.stringify(aiFillResult, null, 2) }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="showAiFillResult = false">取消</el-button>
        <el-button type="primary" @click="applyAiFill">
          <el-icon><Check /></el-icon>
          应用配置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { projectApi } from '@/api'
import { useProjectStore } from '@/stores'

const props = defineProps<{
  config: any
}>()

const emit = defineEmits<{
  (e: 'update', config: any): void
}>()

const projectStore = useProjectStore()

// 折叠面板激活项
const activeCollapse = ref(['script_generation', 'image_generation'])

// 默认配置 - 与后端 Schema 完全对应
const defaultConfig = {
  script_generation: {
    // 基础设定
    genre: null,
    audience_taste: null,
    narrative_perspective: null,
    writing_style: null,
    pacing: null,
    climax_position: null,
    // 主线设定
    world_setting: null,
    golden_finger: null,
    conflict_type: null,
    twist_frequency: null,
    // 角色设定
    protagonist: {
      name: null,
      gender: null,
      age: null,
      personality: null,
      background: null
    },
    supporting_characters_count: null,
    // 长度目标
    target_word_count: null,
    target_duration_minutes: 10,
    segment_word_count: null,
    // 合规设置
    no_violence: true,
    no_adult_content: true,
    no_sensitive_topics: true,
    // 高级设置
    system_prompt_template: null,
    require_visual_prompts: true,
    require_segment_titles: true
  },
  segmenter: {
    strategy: '按镜头脚本',
    min_segment_length: 50,
    max_segment_length: 500,
    require_narration: true,
    require_visual_prompt: true,
    require_mood: false,
    require_shot_type: false
  },
  image_generation: {
    engine: 'pollinations',  // 'pollinations' 或 'comfyui'
    pollinations_model: 'flux',
    style: '国风',
    resolution: '1024',
    aspect_ratio: '竖屏9:16',
    // ComfyUI 特有
    workflow_id: null,
    steps: 20,
    cfg_scale: 7,
    sampler: 'euler_ancestral',
    seed: null,
    negative_prompt: 'low quality, blurry, watermark, text, logo, bad anatomy',
    // 通用
    candidates_per_segment: 3,
    parallel_generation: false,
    max_retries: 3,
    fallback_workflow_id: null,
    character_lora_id: null,
    reference_image_id: null
  },
  // 保留 comfyui 字段以兼容旧数据
  comfyui: {
    workflow_id: null,
    style: '国风',
    resolution: '1024',
    aspect_ratio: '竖屏9:16',
    steps: 20,
    cfg_scale: 7,
    sampler: 'euler_ancestral',
    seed: null,
    negative_prompt: 'low quality, blurry, watermark, text, logo, bad anatomy',
    candidates_per_segment: 3,
    parallel_generation: false,
    max_retries: 3,
    fallback_workflow_id: null,
    character_lora_id: null,
    reference_image_id: null
  },
  tts: {
    engine: 'free_tts',
    voice_type: '男-青年',
    custom_voice_id: null,
    speed: 1.0,
    volume: 1.0,
    pitch: 1.0,
    output_format: 'mp3',
    pause_between_sentences: 0.3,
    emotion: null
  },
  video_composer: {
    frame_rate: '30',
    resolution: '1080p',
    is_portrait: true,
    transition_type: '淡入淡出',
    transition_duration: 0.3,
    bgm_enabled: false,
    bgm_asset_id: null,
    bgm_volume: 0.3,
    bgm_ducking: true,
    subtitle_enabled: true,
    subtitle_format: 'srt',
    subtitle_font: 'Microsoft YaHei',
    subtitle_font_size: 48,
    subtitle_color: '#FFFFFF',
    subtitle_outline: true,
    subtitle_position: '底部',
    watermark_enabled: false,
    watermark_text: null,
    min_segment_duration: 1.5,
    segment_padding: 0.3,
    fallback_chars_per_second: 4.5
  }
}

// 深拷贝创建本地配置
const localConfig = reactive(JSON.parse(JSON.stringify(defaultConfig)))
const saving = ref(false)
const aiFillInput = ref('')
const aiFilling = ref(false)
const showAiFillResult = ref(false)
const aiFillResult = ref<any>(null)
const aiFillExplanation = ref('')

// 深度合并函数
const deepMerge = (target: any, source: any) => {
  for (const key in source) {
    if (source[key] !== null && source[key] !== undefined) {
      if (typeof source[key] === 'object' && !Array.isArray(source[key])) {
        if (!target[key]) target[key] = {}
        deepMerge(target[key], source[key])
      } else {
        target[key] = source[key]
      }
    }
  }
}

// 同步外部配置
watch(() => props.config, (newConfig) => {
  if (newConfig && Object.keys(newConfig).length > 0) {
    // 先重置为默认值
    Object.assign(localConfig, JSON.parse(JSON.stringify(defaultConfig)))
    // 再合并外部配置
    deepMerge(localConfig, newConfig)
  }
}, { immediate: true, deep: true })

const handleSave = async () => {
  saving.value = true
  try {
    emit('update', JSON.parse(JSON.stringify(localConfig)))
    ElMessage.success('配置已保存')
  } finally {
    saving.value = false
  }
}

const handleReset = () => {
  Object.assign(localConfig, JSON.parse(JSON.stringify(defaultConfig)))
  ElMessage.info('已重置为默认配置')
}

const handleAiFill = async () => {
  if (!aiFillInput.value.trim()) {
    ElMessage.warning('请输入配置描述')
    return
  }
  
  if (!projectStore.currentProject) {
    ElMessage.error('项目信息未加载')
    return
  }
  
  aiFilling.value = true
  try {
    const result: any = await projectApi.aiFill(projectStore.currentProject.id, {
      description: aiFillInput.value,
      only_fill_empty: false
    })
    aiFillResult.value = result.suggested_config
    aiFillExplanation.value = result.explanation || ''
    showAiFillResult.value = true
  } catch (error: any) {
    ElMessage.error('AI 助填失败：' + (error.message || '未知错误'))
  } finally {
    aiFilling.value = false
  }
}

const applyAiFill = () => {
  if (aiFillResult.value) {
    // 深度合并配置，只覆盖非空值
    deepMerge(localConfig, aiFillResult.value)
    showAiFillResult.value = false
    ElMessage.success('配置已应用')
  }
}
</script>

<style scoped lang="scss">
.config-panel {
  max-width: 1400px;
}

.ai-fill-section {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  
  .ai-fill-input {
    flex: 1;
    
    :deep(.el-textarea__inner) {
      background: rgba(255, 255, 255, 0.95);
    }
  }
  
  .ai-fill-btn {
    align-self: flex-end;
    background: #fff;
    color: #667eea;
    border: none;
    
    &:hover {
      background: rgba(255, 255, 255, 0.9);
    }
  }
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.config-subsection {
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  
  h4 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #606266;
    padding-bottom: 8px;
    border-bottom: 1px dashed #dcdfe6;
    
    .el-tag {
      margin-left: 8px;
      vertical-align: middle;
    }
  }
}

.engine-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.engine-desc {
  font-size: 12px;
  color: #909399;
  margin-left: 24px;
  margin-top: 2px;
}

:deep(.el-radio) {
  display: block;
  margin-bottom: 12px;
  height: auto;
  line-height: 1.5;
}

.form-actions {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 12px;
}

.form-tip {
  margin-left: 8px;
  font-size: 12px;
  color: #909399;
}

.ai-fill-result {
  .result-hint {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    color: #409eff;
    font-weight: 500;
  }
  
  .result-explanation {
    margin-bottom: 16px;
    padding: 12px 16px;
    background: #f0f9eb;
    border-radius: 8px;
    color: #67c23a;
  }
  
  .result-preview {
    background: #f5f7fa;
    border-radius: 8px;
    padding: 16px;
    max-height: 400px;
    overflow: auto;
    
    pre {
      margin: 0;
      font-size: 13px;
      line-height: 1.6;
      font-family: 'Consolas', 'Monaco', monospace;
    }
  }
}

:deep(.el-collapse-item__header) {
  font-size: 15px;
  height: 50px;
  background: #f5f7fa;
  padding: 0 16px;
  border-radius: 8px;
  margin-bottom: 8px;
}

:deep(.el-collapse-item__content) {
  padding: 20px 0;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
