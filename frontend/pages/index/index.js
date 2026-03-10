// pages/index/index.js
// 获取应用实例
const app = getApp()

// 后端 API 地址（本地开发）
const API_BASE_URL = (app && app.globalData && app.globalData.apiBaseUrl) || 'http://127.0.0.1:18080'
const STUDENT_PROFILE_KEY = 'student_profile'

Page({
  data: {
    // 作业列表
    assignments: [],
    loadingAssignments: false,

    // 快速批改弹窗
    showQuickCorrect: false,

    // 批改状态
    isProcessing: false,
    imageUrl: '',
    statusText: '',
    statusClass: '',
    submissionId: '',
    pollTimer: null,
    result: null,
    tempFilePath: '',
    userProfile: null,
  },

  onLoad() {
    console.log('首页加载完成')
    console.log('后端地址:', API_BASE_URL)
    this.loadStudentProfile()
    this.loadAssignments()
  },

  onShow() {
    // 每次显示页面时刷新作业列表
    if (this.data.userProfile) {
      this.loadAssignments()
    }
  },

  onUnload() {
    this.clearPollTimer()
  },


  goTeacherPage() {
    wx.navigateTo({
      url: '/pages/teacher/index'
    })
  },
  loadStudentProfile() {
    const fromGlobal = app && app.globalData ? app.globalData.studentProfile : null
    if (fromGlobal && fromGlobal.nickName) {
      this.setData({ userProfile: fromGlobal })
      return
    }

    try {
      const cached = wx.getStorageSync(STUDENT_PROFILE_KEY)
      if (cached && cached.nickName) {
        if (app && app.globalData) {
          app.globalData.studentProfile = cached
        }
        this.setData({ userProfile: cached })
      }
    } catch (err) {
      console.warn('读取学生登录态失败:', err)
    }
  },

  // ===== 登录学生账号（微信授权信息） =====
  loginStudent() {
    wx.getUserProfile({
      desc: '用于标识你的作业批改记录',
      lang: 'zh_CN',
      success: (res) => {
        const userInfo = res.userInfo || {}
        const profile = {
          nickName: userInfo.nickName || '微信同学',
          avatarUrl: userInfo.avatarUrl || '',
          gender: userInfo.gender || 0,
          province: userInfo.province || '',
          city: userInfo.city || '',
          loginAt: Date.now(),
        }

        if (app && app.globalData) {
          app.globalData.studentProfile = profile
        }

        wx.setStorageSync(STUDENT_PROFILE_KEY, profile)
        this.setData({ userProfile: profile })
        wx.showToast({ title: '登录成功', icon: 'success' })
      },
      fail: (err) => {
        console.warn('微信登录取消/失败:', err)
        if (err && err.errMsg && err.errMsg.includes('cancel')) {
          return
        }
        wx.showToast({ title: '登录失败，请重试', icon: 'none' })
      }
    })
  },

  // ===== 加载作业列表 =====
  async loadAssignments() {
    this.setData({ loadingAssignments: true })
    try {
      const assignments = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments`,
      })

      const now = new Date()
      const processedAssignments = (assignments || []).map(item => {
        const endTime = item.submit_end_time ? new Date(item.submit_end_time) : null
        const startTime = item.submit_start_time ? new Date(item.submit_start_time) : null

        let statusClass = 'draft'
        let statusText = '待开始'
        let isNearDeadline = false
        let countdown = ''

        if (item.publish_status === 'published') {
          if (endTime && now > endTime) {
            statusClass = 'ended'
            statusText = '已截止'
          } else if (startTime && now < startTime) {
            statusClass = 'draft'
            statusText = '待开始'
          } else {
            statusClass = 'active'
            statusText = '进行中'
            // 计算倒计时
            if (endTime) {
              const diff = endTime - now
              if (diff < 24 * 60 * 60 * 1000) {
                isNearDeadline = true
                statusClass = 'near-deadline'
                statusText = '即将截止'
                const hours = Math.floor(diff / (60 * 60 * 1000))
                const minutes = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000))
                countdown = `还剩 ${hours}小时${minutes}分`
              } else {
                const days = Math.floor(diff / (24 * 60 * 60 * 1000))
                countdown = `还剩 ${days} 天`
              }
            }
          }
        }

        const submitted = item.submitted_count || 0
        const total = item.total_students || 30
        const progressPercent = total > 0 ? Math.round((submitted / total) * 100) : 0

        return {
          ...item,
          statusClass,
          statusText,
          isNearDeadline,
          countdown,
          progress: `${submitted}/${total}`,
          progressPercent: Math.min(progressPercent, 100)
        }
      })

      // 按状态排序：进行中 > 即将截止 > 待开始 > 已截止
      const orderMap = { 'near-deadline': 0, 'active': 1, 'draft': 2, 'ended': 3 }
      processedAssignments.sort((a, b) => orderMap[a.statusClass] - orderMap[b.statusClass])

      this.setData({ assignments: processedAssignments })
    } catch (err) {
      console.warn('加载作业列表失败:', err)
      // 静默失败，不打扰用户
    } finally {
      this.setData({ loadingAssignments: false })
    }
  },

  // ===== 进入作业详情 =====
  goToAssignment(e) {
    const id = e.currentTarget.dataset.id
    const assignment = this.data.assignments.find(a => a.id === id)
    if (!assignment) return

    // 跳转到作业详情页
    wx.navigateTo({
      url: `/pages/assignment/detail?id=${id}`
    })
  },

  // ===== 快速批改弹窗 =====
  showQuickCorrect() {
    this.setData({ showQuickCorrect: true })
  },

  hideQuickCorrect() {
    this.setData({ showQuickCorrect: false })
  },

  // ===== 通用请求方法 =====
  requestJson({ url, method = 'GET', data = null }) {
    return new Promise((resolve, reject) => {
      wx.request({
        url,
        method,
        data,
        header: { 'Content-Type': 'application/json' },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data)
          } else {
            reject(new Error(res.data?.detail || `请求失败 (${res.statusCode})`))
          }
        },
        fail: () => reject(new Error('网络请求失败')),
      })
    })
  },

  logoutStudent() {
    wx.showModal({
      title: '退出登录',
      content: '退出后将需要重新授权微信信息，是否继续？',
      confirmText: '退出',
      success: (res) => {
        if (!res.confirm) return

        if (app && app.globalData) {
          app.globalData.studentProfile = null
        }

        try {
          wx.removeStorageSync(STUDENT_PROFILE_KEY)
        } catch (err) {
          console.warn('清理学生登录态失败:', err)
        }

        this.setData({ userProfile: null })
        wx.showToast({ title: '已退出', icon: 'none' })
      }
    })
  },

  getStudentName() {
    const profile = this.data.userProfile
    return (profile && profile.nickName) ? profile.nickName : '未登录学生'
  },

  // ===== 将 LaTeX 转为图片 HTML =====
  latexToHtml(text) {
    if (!text) return ''

    // 修复后端双重转义的问题（\\int -> \int）
    let fixed = text.replace(/\\\\/g, '\\')

    // 转换 $...$ 包裹的公式为图片
    return fixed.replace(/\$([^$]+)\$/g, (match, latex) => {
      const encoded = encodeURIComponent(latex.trim())
      return `<img src="https://latex.codecogs.com/png.latex?\\dpi{150}${encoded}" style="display:inline-block;vertical-align:middle;height:1.4em;max-width:100%;" />`
    })
  },

  // ===== 选择图片 =====
  chooseImage() {
    if (this.data.isProcessing) return

    if (!this.data.userProfile) {
      wx.showToast({ title: '请先登录学生账号', icon: 'none' })
      return
    }

    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      camera: 'back',
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath
        this.setData({
          imageUrl: tempFilePath,
          tempFilePath: tempFilePath,
          result: null,
          statusText: '准备上传...',
          statusClass: 'processing'
        })
        this.quickCorrect(tempFilePath)
      },
      fail: (err) => {
        console.error('选择图片失败:', err)
        if (err.errMsg && !err.errMsg.includes('cancel')) {
          wx.showToast({ title: '选择图片失败', icon: 'none' })
        }
      }
    })
  },

  // ===== 清除定时器 =====
  clearPollTimer() {
    if (this.data.pollTimer) {
      clearInterval(this.data.pollTimer)
      this.setData({ pollTimer: null })
    }
  },

  // ===== 错误处理 =====
  handleError(message) {
    this.clearPollTimer()
    wx.hideLoading()
    this.setData({
      isProcessing: false,
      statusText: '错误: ' + message,
      statusClass: 'error'
    })
    wx.showToast({ title: message, icon: 'none', duration: 3000 })
  },

  // ===== 使用快速批改接口 =====
  quickCorrect(filePath) {
    this.setData({
      isProcessing: true,
      statusText: 'AI批改中（约需10-30秒）...',
      statusClass: 'processing'
    })

    // 设置超时定时器（60秒）
    let timeoutTimer = setTimeout(() => {
      this.handleError('请求超时，请检查网络或稍后重试')
    }, 60000)

    const clearTimeoutTimer = () => {
      if (timeoutTimer) {
        clearTimeout(timeoutTimer)
        timeoutTimer = null
      }
    }

    wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/correct/upload`,
      filePath: filePath,
      name: 'file',
      formData: {
        student_name: this.getStudentName(),
      },
      header: { 'Accept': 'application/json' },
      success: (res) => {
        clearTimeoutTimer()
        wx.hideLoading()
        if (res.statusCode === 200) {
          try {
            const data = JSON.parse(res.data)
            console.log('批改结果:', data)

            const questions = (data.questions || []).map(q => {
              let score = q.score
              if (typeof score === 'string') {
                score = parseFloat(score)
              }
              if (score === undefined || score === null || Number.isNaN(score)) {
                score = q.is_correct === true ? 10 : 0
              }
              score = score || 0

              let maxScore = q.max_score
              if (typeof maxScore === 'string') {
                maxScore = parseFloat(maxScore)
              }
              if (maxScore === undefined || maxScore === null || Number.isNaN(maxScore)) {
                maxScore = 10
              }

              const percent = Math.round(score / maxScore * 100)

              return {
                ...q,
                score: score,
                max_score: maxScore,
                content: this.latexToHtml(q.content),
                student_ans: this.latexToHtml(q.student_ans),
                analysis: this.latexToHtml(q.analysis),
                _barWidth: percent,
                _barClass: percent >= 60 ? 'good' : 'bad',
                _percent: percent,
                _statusClass: score >= maxScore ? 'correct-tag' : score > 0 ? 'partial-tag' : 'wrong-tag',
                _statusText: score >= maxScore ? '正确' : score > 0 ? '部分正确' : '错误',
                _showPartial: score > 0 && score < maxScore
              }
            })

            const ocrText = data._ocr_extracted || ''

            this.setData({
              isProcessing: false,
              statusText: '批改完成',
              statusClass: 'completed',
              result: {
                student_name: this.getStudentName(),
                questions: questions,
                total_score: questions.reduce((sum, q) => sum + (q.score || 0), 0),
                max_total_score: questions.reduce((sum, q) => sum + (q.max_score || 10), 0),
                ocrText: ocrText,
              }
            })
            wx.showToast({ title: '批改完成', icon: 'success' })
          } catch (e) {
            console.error('解析响应失败:', e, res.data)
            this.handleError('解析结果失败')
          }
        } else {
          let msg = '批改失败 (' + res.statusCode + ')'
          try {
            const err = JSON.parse(res.data)
            msg = err.detail?.message || err.detail || msg
          } catch (e) {}
          this.handleError(msg)
        }
      },
      fail: (err) => {
        clearTimeoutTimer()
        console.error('请求失败:', err)
        this.handleError('网络连接失败，请检查后端服务')
      }
    })

    wx.showLoading({ title: 'AI批改中...', mask: true })
  }
})

