// pages/admin/index.js
const app = getApp()
const API_BASE_URL = (app && app.globalData && app.globalData.apiBaseUrl) || 'http://127.0.0.1:18080'

Page({
  data: {
    // 登录状态
    isLoggedIn: false,
    password: '',

    // 系统状态
    currentConfig: {
      AI_VISION_API_BASE_URL: '',
      AI_VISION_MODEL_NAME: '',
      AI_TEXT_API_BASE_URL: '',
      AI_TEXT_MODEL_NAME: '',
    },
    aiStatus: {
      vision: false,
      text: false,
    },
    testing: false,

    // 表单配置
    configForm: {
      visionBaseUrl: '',
      visionKey: '',
      visionModel: '',
      textBaseUrl: '',
      textKey: '',
      textModel: '',
      solveBaseUrl: '',
      solveKey: '',
      solveModel: '',
    },

    // 模型列表
    modelLists: {
      vision: [],
      visionSelectedIndex: -1,
      visionSelectedDesc: '',
      text: [],
      textSelectedIndex: -1,
      textSelectedDesc: '',
      solve: [],
      solveSelectedIndex: -1,
      solveSelectedDesc: '',
    },
    fetchingModels: {
      vision: false,
      text: false,
      solve: false,
    },

    // 保存状态
    saving: false,
    saveResult: {
      show: false,
      success: false,
      message: '',
    },
  },

  onLoad() {
    // 检查本地是否有登录态
    const savedPassword = wx.getStorageSync('admin_password')
    if (savedPassword) {
      this.setData({ password: savedPassword })
      this.login()
    }
  },

  onShow() {
    if (this.data.isLoggedIn) {
      this.loadConfig()
    }
  },

  // ========== 登录相关 ==========

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  async login() {
    const password = this.data.password.trim()
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }

    wx.showLoading({ title: '验证中...' })

    try {
      const res = await this.request({
        url: `${API_BASE_URL}/api/v1/admin/login`,
        method: 'POST',
        data: { password }
      })

      if (res.success) {
        wx.setStorageSync('admin_password', password)
        this.setData({ isLoggedIn: true })
        this.loadConfig()
        wx.showToast({ title: '登录成功', icon: 'success' })
      } else {
        wx.showToast({ title: '密码错误', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '登录失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  logout() {
    wx.removeStorageSync('admin_password')
    this.setData({
      isLoggedIn: false,
      password: '',
    })
  },

  // ========== 配置管理 ==========

  async loadConfig() {
    const password = wx.getStorageSync('admin_password')
    if (!password) return

    try {
      const config = await this.request({
        url: `${API_BASE_URL}/api/v1/admin/config`,
        header: { 'X-Admin-Password': password }
      })

      this.setData({
        currentConfig: config,
        aiStatus: {
          vision: !!config.AI_VISION_MODEL_NAME,
          text: !!config.AI_TEXT_MODEL_NAME,
          solve: !!config.SOLVE_MODEL_NAME,
        },
        // 同步到表单（不填充敏感信息如Key）
        configForm: {
          visionBaseUrl: config.AI_VISION_API_BASE_URL || '',
          visionKey: '', // 不回显Key
          visionModel: config.AI_VISION_MODEL_NAME || '',
          textBaseUrl: config.AI_TEXT_API_BASE_URL || '',
          textKey: '', // 不回显Key
          textModel: config.AI_TEXT_MODEL_NAME || '',
          solveBaseUrl: config.SOLVE_API_BASE_URL || '',
          solveKey: '', // 不回显Key
          solveModel: config.SOLVE_MODEL_NAME || '',
        }
      })
    } catch (err) {
      wx.showToast({ title: '加载配置失败', icon: 'none' })
    }
  },

  onConfigInput(e) {
    const key = e.currentTarget.dataset.key
    if (!key) return
    this.setData({ [`configForm.${key}`]: e.detail.value })
  },

  resetForm() {
    this.loadConfig()
    wx.showToast({ title: '已重置', icon: 'none' })
  },

  async saveConfig() {
    const password = wx.getStorageSync('admin_password')
    if (!password) {
      this.logout()
      return
    }

    const { configForm } = this.data

    // 收集有值的更新
    const updates = { password }

    if (configForm.visionBaseUrl.trim()) {
      updates.AI_VISION_API_BASE_URL = configForm.visionBaseUrl.trim()
    }
    if (configForm.visionKey.trim()) {
      updates.AI_VISION_API_KEY = configForm.visionKey.trim()
    }
    if (configForm.visionModel.trim()) {
      updates.AI_VISION_MODEL_NAME = configForm.visionModel.trim()
    }
    if (configForm.textBaseUrl.trim()) {
      updates.AI_TEXT_API_BASE_URL = configForm.textBaseUrl.trim()
    }
    if (configForm.textKey.trim()) {
      updates.AI_TEXT_API_KEY = configForm.textKey.trim()
    }
    if (configForm.textModel.trim()) {
      updates.AI_TEXT_MODEL_NAME = configForm.textModel.trim()
    }
    if (configForm.solveBaseUrl.trim()) {
      updates.SOLVE_API_BASE_URL = configForm.solveBaseUrl.trim()
    }
    if (configForm.solveKey.trim()) {
      updates.SOLVE_API_KEY = configForm.solveKey.trim()
    }
    if (configForm.solveModel.trim()) {
      updates.SOLVE_MODEL_NAME = configForm.solveModel.trim()
    }

    if (Object.keys(updates).length <= 1) {
      wx.showToast({ title: '没有要更新的配置', icon: 'none' })
      return
    }

    this.setData({ saving: true })

    try {
      const res = await this.request({
        url: `${API_BASE_URL}/api/v1/admin/config`,
        method: 'POST',
        data: updates
      })

      if (res.success) {
        this.showSaveResult(true, '配置已更新并立即生效')
        // 清空Key输入框（安全考虑）
        this.setData({
          'configForm.visionKey': '',
          'configForm.textKey': '',
          'configForm.solveKey': '',
        })
        // 刷新配置显示
        this.loadConfig()
      } else {
        this.showSaveResult(false, res.message || '更新失败')
      }
    } catch (err) {
      this.showSaveResult(false, err.message || '保存失败')
    } finally {
      this.setData({ saving: false })
    }
  },

  showSaveResult(success, message) {
    this.setData({
      saveResult: { show: true, success, message }
    })
    setTimeout(() => {
      this.setData({ 'saveResult.show': false })
    }, 3000)
  },

  // ========== 获取模型列表 ==========

  async fetchModelList(type) {
    const password = wx.getStorageSync('admin_password')
    if (!password) return

    const baseUrlKey = `${type}BaseUrl`
    const keyKey = `${type}Key`
    const baseUrl = this.data.configForm[baseUrlKey]
    const apiKey = this.data.configForm[keyKey]

    if (!baseUrl || !apiKey) {
      wx.showToast({ title: '请先填写 Base URL 和 API Key', icon: 'none' })
      return
    }

    this.setData({ [`fetchingModels.${type}`]: true })

    try {
      const res = await this.request({
        url: `${API_BASE_URL}/api/v1/admin/models`,
        method: 'POST',
        data: {
          api_key: apiKey,
          base_url: baseUrl
        },
        header: { 'X-Admin-Password': password }
      })

      if (res.success && res.models) {
        this.setData({
          [`modelLists.${type}`]: res.models,
          [`modelLists.${type}SelectedIndex`]: -1,
          [`modelLists.${type}SelectedDesc`]: '',
        })

        wx.showToast({
          title: `获取到 ${res.models.length} 个模型`,
          icon: 'success'
        })
      } else {
        // 即使失败也显示返回的模型列表（可能是硬编码的）
        if (res.models && res.models.length > 0) {
          this.setData({
            [`modelLists.${type}`]: res.models,
            [`modelLists.${type}SelectedIndex`]: -1,
            [`modelLists.${type}SelectedDesc`]: '',
          })
        }
        wx.showToast({ title: res.message || '获取失败', icon: 'none', duration: 3000 })
      }
    } catch (err) {
      wx.showToast({ title: err.message || '请求失败', icon: 'none' })
    } finally {
      this.setData({ [`fetchingModels.${type}`]: false })
    }
  },

  fetchVisionModels() {
    this.fetchModelList('vision')
  },

  fetchTextModels() {
    this.fetchModelList('text')
  },

  fetchSolveModels() {
    this.fetchModelList('solve')
  },

  onVisionModelSelect(e) {
    const index = e.detail.value
    const model = this.data.modelLists.vision[index]
    if (model) {
      this.setData({
        'configForm.visionModel': model.id,
        'modelLists.visionSelectedIndex': index,
        'modelLists.visionSelectedDesc': model.description || '',
      })
    }
  },

  onTextModelSelect(e) {
    const index = e.detail.value
    const model = this.data.modelLists.text[index]
    if (model) {
      this.setData({
        'configForm.textModel': model.id,
        'modelLists.textSelectedIndex': index,
        'modelLists.textSelectedDesc': model.description || '',
      })
    }
  },

  onSolveModelSelect(e) {
    const index = e.detail.value
    const model = this.data.modelLists.solve[index]
    if (model) {
      this.setData({
        'configForm.solveModel': model.id,
        'modelLists.solveSelectedIndex': index,
        'modelLists.solveSelectedDesc': model.description || '',
      })
    }
  },

  // ========== 测试连接 ==========

  async testConnection() {
    const password = wx.getStorageSync('admin_password')
    if (!password) return

    this.setData({ testing: true })

    try {
      const res = await this.request({
        url: `${API_BASE_URL}/api/v1/admin/config/test`,
        header: { 'X-Admin-Password': password }
      })

      const visionOk = res.details && res.details.vision && res.details.vision.configured
      const textOk = res.details && res.details.text && res.details.text.configured
      const solveOk = res.details && res.details.solve && res.details.solve.configured

      this.setData({
        aiStatus: {
          vision: visionOk,
          text: textOk,
          solve: solveOk,
        }
      })

      if (visionOk || textOk) {
        wx.showToast({ title: '配置检查通过', icon: 'success' })
      } else {
        wx.showToast({ title: '配置不完整', icon: 'none' })
      }
    } catch (err) {
      wx.showToast({ title: '测试失败', icon: 'none' })
    } finally {
      this.setData({ testing: false })
    }
  },

  // ========== 网络请求封装 ==========

  request({ url, method = 'GET', data = null, header = {} }) {
    return new Promise((resolve, reject) => {
      wx.request({
        url,
        method,
        data,
        header: {
          'Content-Type': 'application/json',
          ...header,
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data)
            return
          }

          const detail = res.data && res.data.detail
          const message = typeof detail === 'string'
            ? detail
            : (detail && detail.message) || `请求失败 (${res.statusCode})`
          reject(new Error(message))
        },
        fail: () => reject(new Error('网络请求失败')),
      })
    })
  },
})
