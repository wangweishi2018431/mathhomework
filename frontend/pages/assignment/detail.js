// pages/assignment/detail.js
const app = getApp()
const API_BASE_URL = (app && app.globalData && app.globalData.apiBaseUrl) || 'http://127.0.0.1:18080'

Page({
  data: {
    assignmentId: '',
    assignment: null,
    loading: true,
    error: '',

    // 提交状态
    hasSubmitted: false,
    submission: null,

    // 上传相关
    isUploading: false,
    imageUrl: '',
    tempFilePath: '',
  },

  onLoad(options) {
    const { id } = options
    if (!id) {
      wx.showToast({ title: '作业ID缺失', icon: 'none' })
      wx.navigateBack()
      return
    }

    this.setData({ assignmentId: id })
    this.loadAssignmentDetail()
  },

  onShow() {
    // 每次显示时刷新状态
    if (this.data.assignmentId) {
      this.loadSubmissionStatus()
    }
  },

  onPullDownRefresh() {
    Promise.all([
      this.loadAssignmentDetail(),
      this.loadSubmissionStatus()
    ]).finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 加载作业详情
  async loadAssignmentDetail() {
    this.setData({ loading: true, error: '' })

    try {
      const assignment = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${this.data.assignmentId}`,
      })

      // 处理时间显示
      const now = new Date()
      const endTime = assignment.submit_end_time ? new Date(assignment.submit_end_time) : null
      const startTime = assignment.submit_start_time ? new Date(assignment.submit_start_time) : null

      let statusText = '进行中'
      let statusClass = 'active'
      let canSubmit = true
      let timeStatus = ''

      if (assignment.publish_status !== 'published') {
        statusText = '未发布'
        statusClass = 'draft'
        canSubmit = false
      } else if (endTime && now > endTime) {
        statusText = '已截止'
        statusClass = 'ended'
        canSubmit = assignment.allow_late
        timeStatus = '已截止'
      } else if (startTime && now < startTime) {
        statusText = '未开始'
        statusClass = 'pending'
        canSubmit = false
        timeStatus = `开始时间: ${this.formatTime(assignment.submit_start_time)}`
      } else if (endTime) {
        const diff = endTime - now
        const days = Math.floor(diff / (24 * 60 * 60 * 1000))
        const hours = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000))

        if (days > 0) {
          timeStatus = `还剩 ${days} 天 ${hours} 小时`
        } else {
          timeStatus = `还剩 ${hours} 小时`
          statusClass = 'near'
        }
      }

      this.setData({
        assignment: {
          ...assignment,
          statusText,
          statusClass,
          canSubmit,
          timeStatus,
          formattedStartTime: this.formatTime(assignment.submit_start_time),
          formattedEndTime: this.formatTime(assignment.submit_end_time),
          formattedAppealTime: this.formatTime(assignment.appeal_end_time),
        },
        loading: false,
      })

      // 加载提交状态
      this.loadSubmissionStatus()
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '加载作业详情失败'
      })
    }
  },

  // 加载学生的提交状态
  async loadSubmissionStatus() {
    try {
      // 获取该作业的所有提交
      const submissions = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${this.data.assignmentId}/submissions`,
      })

      // 获取当前学生名称
      const studentName = this.getStudentName()

      // 查找当前学生的提交
      const mySubmission = submissions.find(s => s.student_name === studentName)

      if (mySubmission) {
        this.setData({
          hasSubmitted: true,
          submission: mySubmission,
        })
      }
    } catch (err) {
      console.warn('加载提交状态失败:', err)
    }
  },

  getStudentName() {
    const profile = wx.getStorageSync('student_profile')
    return profile?.nickName || '未知学生'
  },

  formatTime(isoTime) {
    if (!isoTime) return '未设置'
    const date = new Date(isoTime)
    return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  },

  // 选择图片并提交
  chooseAndSubmit() {
    if (!this.data.assignment?.canSubmit) {
      wx.showToast({ title: '当前不可提交', icon: 'none' })
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
        })
        this.submitAssignment(tempFilePath)
      },
    })
  },

  // 提交作业
  submitAssignment() {
    const filePath = this.data.tempFilePath
    if (!filePath) {
      wx.showToast({ title: '请先选择图片', icon: 'none' })
      return
    }

    this.setData({ isUploading: true })

    wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/assignments/${this.data.assignmentId}/submit`,
      filePath: filePath,
      name: 'file',
      formData: {
        student_name: this.getStudentName(),
      },
      success: (res) => {
        if (res.statusCode === 202) {
          const data = JSON.parse(res.data)
          wx.showToast({ title: '提交成功', icon: 'success' })

          this.setData({
            hasSubmitted: true,
            submission: {
              id: data.submission_id,
              status: 'processing',
            },
          })

          // 开始轮询批改状态
          this.pollSubmissionStatus(data.submission_id)
        } else {
          let msg = '提交失败'
          try {
            const err = JSON.parse(res.data)
            msg = err.detail || msg
          } catch (e) {}
          wx.showToast({ title: msg, icon: 'none' })
        }
      },
      fail: () => {
        wx.showToast({ title: '网络错误', icon: 'none' })
      },
      complete: () => {
        this.setData({ isUploading: false })
      },
    })
  },

  // 轮询提交状态
  pollSubmissionStatus(submissionId) {
    const poll = () => {
      this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${this.data.assignmentId}/submissions/${submissionId}`,
      }).then(data => {
        this.setData({ submission: data })

        if (data.status === 'processing') {
          // 继续轮询
          setTimeout(poll, 2000)
        } else if (data.status === 'completed') {
          wx.showToast({ title: '批改完成', icon: 'success' })
        } else if (data.status === 'failed') {
          wx.showToast({ title: '批改失败', icon: 'none' })
        }
      }).catch(() => {
        // 轮询失败，停止
      })
    }

    poll()
  },

  // 查看批改结果
  viewResult() {
    const { submission } = this.data
    if (!submission || submission.status !== 'completed') {
      wx.showToast({ title: '批改尚未完成', icon: 'none' })
      return
    }

    // 构建结果数据并跳转结果页（或在本页展示）
    const questions = submission.questions || []
    const resultData = {
      assignment_title: this.data.assignment?.title,
      total_score: submission.total_score,
      max_total_score: submission.max_total_score,
      questions: questions.map(q => ({
        ...q,
        _statusClass: q.score >= q.max_score ? 'correct' : q.score > 0 ? 'partial' : 'wrong',
        _statusText: q.score >= q.max_score ? '正确' : q.score > 0 ? '部分正确' : '错误',
      })),
    }

    // 存储到全局，结果页读取
    app.globalData = app.globalData || {}
    app.globalData.lastResult = resultData

    wx.navigateTo({
      url: '/pages/assignment/result'
    })
  },

  // 重新提交
  resubmit() {
    if (!this.data.assignment?.allow_resubmit) {
      wx.showToast({ title: '该作业不允许重新提交', icon: 'none' })
      return
    }

    wx.showModal({
      title: '重新提交',
      content: '重新提交将覆盖之前的提交记录，是否继续？',
      confirmText: '继续',
      success: (res) => {
        if (res.confirm) {
          this.chooseAndSubmit()
        }
      },
    })
  },

  // 预览图片
  previewImage() {
    if (this.data.imageUrl) {
      wx.previewImage({
        urls: [this.data.imageUrl],
      })
    }
  },

  // 返回首页
  goBack() {
    wx.navigateBack()
  },

  // 通用请求
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
})
