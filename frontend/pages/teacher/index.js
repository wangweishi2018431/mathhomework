// pages/teacher/index.js
const app = getApp()
const API_BASE_URL = (app && app.globalData && app.globalData.apiBaseUrl) || 'http://127.0.0.1:18080'

Page({
  data: {
    // Tab 状态
    activeTab: 'course',

    // 作业管理子 Tab
    assignmentSubTab: 'list', // 'list' | 'create'
    assignments: [],
    loadingAssignments: false,

    // 课程管理
    loadingCourses: false,
    courses: [],
    selectedCourseIndex: -1,
    selectedCourseId: '',
    selectedCourseName: '',
    rosterStudents: [],

    courseIdInput: '',
    courseNameInput: '',

    studentIdInput: '',
    studentNameInput: '',
    classNameInput: '',

    importFilePath: '',
    importFileName: '',

    // 创建作业
    assignmentMode: null, // 'manual' | 'photo' | null
    assignmentTitle: '',

    // 手动输入模式
    questionContent: '',
    maxScoreInput: '10',
    teacherAnswer: '',
    createdAssignment: null,

    // 拍照上传模式
    solveImagePath: '',
    solveImagePreview: '',
    solveSpecifications: '',
    solveLoading: false,
    extractedQuestion: null, // AI识别后可编辑的题目

    // 时间配置
    assignmentStartTime: '',
    assignmentEndTime: '',
    assignmentAppealTime: '',
    dateTimeArray: null,
    dateTimeStart: [0, 0, 0, 0, 0],
    dateTimeEnd: [0, 0, 0, 0, 0],
    dateTimeAppeal: [0, 0, 0, 0, 0],

    // 规则配置
    allowResubmit: true,
    allowLate: true,
    lateRules: ['逾期按100%计分', '逾期按80%计分', '逾期按60%计分', '逾期按0%计分（拒收）'],
    lateRuleIndex: 0,
    lateRuleValues: ['100%', '80%', '60%', '0%'],
  },

  onLoad() {
    this.loadCourses()
    this.loadAssignments()
    this.initDateTimePicker()
  },

  initDateTimePicker() {
    // 初始化时间选择器数据
    const years = []
    const months = []
    const days = []
    const hours = []
    const minutes = []

    // 生成年份（当前年前后5年）
    const currentYear = new Date().getFullYear()
    for (let i = currentYear - 1; i <= currentYear + 5; i++) {
      years.push(i + '年')
    }

    // 生成月份
    for (let i = 1; i <= 12; i++) {
      months.push(i + '月')
    }

    // 生成日期（1-31，实际选择时会根据月份调整）
    for (let i = 1; i <= 31; i++) {
      days.push(i + '日')
    }

    // 生成小时
    for (let i = 0; i < 24; i++) {
      hours.push(i + '时')
    }

    // 生成分钟（间隔5分钟）
    for (let i = 0; i < 60; i += 5) {
      minutes.push(i + '分')
    }

    const dateTimeArray = [years, months, days, hours, minutes]

    // 设置默认值为当前时间
    const now = new Date()
    const defaultIndex = [
      years.indexOf(currentYear + '年'), // 今年
      now.getMonth(), // 当前月
      now.getDate() - 1, // 当前日
      now.getHours(), // 当前小时
      Math.floor(now.getMinutes() / 5) // 当前分钟（取5分钟间隔）
    ]

    this.setData({
      dateTimeArray,
      dateTimeStart: defaultIndex,
      dateTimeEnd: defaultIndex,
      dateTimeAppeal: defaultIndex
    })
  },

  onPullDownRefresh() {
    this.loadCourses().finally(() => wx.stopPullDownRefresh())
  },

  // ========== Tab 切换 ==========

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
    if (tab === 'assignment') {
      this.loadAssignments()
    }
  },

  // ========== 作业管理子 Tab ==========

  switchAssignmentSubTab(e) {
    const subtab = e.currentTarget.dataset.subtab
    this.setData({ assignmentSubTab: subtab })
    if (subtab === 'list') {
      this.loadAssignments()
    }
  },

  async loadAssignments() {
    this.setData({ loadingAssignments: true })
    try {
      const assignments = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments`,
      })

      const now = new Date()
      const processedAssignments = (assignments || []).map(item => {
        const endTime = item.submit_end_time ? new Date(item.submit_end_time.replace(/年|月|日|时|分/g, '-').replace(/-$/, '')) : null
        const startTime = item.submit_start_time ? new Date(item.submit_start_time.replace(/年|月|日|时|分/g, '-').replace(/-$/, '')) : null

        let statusClass = 'draft'
        let statusText = '草稿'
        let isNearDeadline = false

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
            // 24小时内截止显示即将截止
            if (endTime && (endTime - now) < 24 * 60 * 60 * 1000) {
              isNearDeadline = true
              statusClass = 'near-deadline'
              statusText = '即将截止'
            }
          }
        }

        const submitted = item.submitted_count || 0
        const total = item.total_students || 30  // 默认假设30人班级
        const progressPercent = total > 0 ? Math.round((submitted / total) * 100) : 0

        return {
          ...item,
          statusClass,
          statusText,
          isNearDeadline,
          progressPercent: Math.min(progressPercent, 100),
          progress: `${submitted}/${total}`  // 覆盖后端返回的progress
        }
      })

      this.setData({
        assignments: processedAssignments
      })
    } catch (err) {
      wx.showToast({ title: err.message || '加载作业列表失败', icon: 'none' })
    } finally {
      this.setData({ loadingAssignments: false })
    }
  },

  viewAssignmentDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '作业详情',
      content: `作业ID: ${id}\n\n功能开发中...`,
      showCancel: false
    })
  },

  showExtendDeadline(e) {
    const id = e.currentTarget.dataset.id
    const currentEndTime = e.currentTarget.dataset.endtime || '未设置'

    wx.showModal({
      title: '延长截止时间',
      content: `当前截止时间: ${currentEndTime}\n\n请在下方选择新的截止时间`,
      confirmText: '选择时间',
      success: (res) => {
        if (res.confirm) {
          // 显示时间选择器
          this.showDateTimePickerForExtend(id)
        }
      }
    })
  },

  showDateTimePickerForExtend(assignmentId) {
    // 保存当前正在延长的作业ID
    this.setData({ extendingAssignmentId: assignmentId })

    // 使用微信的日期时间选择
    wx.showActionSheet({
      itemList: ['延长1天', '延长3天', '延长7天', '自定义时间'],
      success: (res) => {
        const days = [1, 3, 7][res.tapIndex]
        if (days) {
          this.extendDeadline(assignmentId, days)
        } else {
          // 自定义时间 - 这里简化处理，使用默认延长7天
          this.extendDeadline(assignmentId, 7)
        }
      }
    })
  },

  async extendDeadline(assignmentId, days) {
    wx.showLoading({ title: '更新中...', mask: true })

    try {
      // 获取当前作业详情
      const assignment = this.data.assignments.find(a => a.id === assignmentId)
      if (!assignment) {
        throw new Error('作业不存在')
      }

      // 计算新的截止时间
      const currentEndTime = assignment.submit_end_time
        ? new Date(assignment.submit_end_time.replace(/年|月|日|时|分/g, '-').replace(/-$/, ''))
        : new Date()
      const newEndTime = new Date(currentEndTime.getTime() + days * 24 * 60 * 60 * 1000)

      // 格式化为后端需要的格式
      const formatDateTime = (date) => {
        const y = date.getFullYear()
        const m = String(date.getMonth() + 1).padStart(2, '0')
        const d = String(date.getDate()).padStart(2, '0')
        const h = String(date.getHours()).padStart(2, '0')
        const min = String(date.getMinutes()).padStart(2, '0')
        return `${y}-${m}-${d}T${h}:${min}:00`
      }

      // 调用更新接口 - 使用现有的创建接口修改（暂时用PATCH方式）
      // 注意：后端需要添加 PATCH /assignments/{id} 接口
      await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${assignmentId}/extend`,
        method: 'POST',
        data: {
          submit_end_time: formatDateTime(newEndTime)
        }
      })

      wx.showToast({ title: `已延长${days}天`, icon: 'success' })
      this.loadAssignments()
    } catch (err) {
      wx.showToast({ title: err.message || '延长失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  goToAdmin() {
    wx.navigateTo({
      url: '/pages/admin/index'
    })
  },

  // ========== 通用输入处理 ==========

  onFieldInput(e) {
    const key = e.currentTarget.dataset.key
    if (!key) return
    this.setData({ [key]: e.detail.value })
  },

  // ========== 课程管理 ==========

  async loadCourses() {
    this.setData({ loadingCourses: true })

    try {
      const courses = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/courses`,
      })

      const list = Array.isArray(courses) ? courses : []
      let selectedCourseIndex = this.data.selectedCourseIndex

      if (!list.length) {
        this.setData({
          courses: [],
          selectedCourseIndex: -1,
          selectedCourseId: '',
          selectedCourseName: '',
          rosterStudents: [],
        })
        return
      }

      const oldId = this.data.selectedCourseId
      if (oldId) {
        const idx = list.findIndex(c => c.course_id === oldId)
        selectedCourseIndex = idx >= 0 ? idx : 0
      } else {
        selectedCourseIndex = 0
      }

      const selected = list[selectedCourseIndex]
      this.setData({
        courses: list,
        selectedCourseIndex,
        selectedCourseId: selected.course_id,
        selectedCourseName: selected.course_name,
        rosterStudents: selected.students || [],
      })
    } catch (err) {
      wx.showToast({ title: err.message || '加载课程失败', icon: 'none' })
    } finally {
      this.setData({ loadingCourses: false })
    }
  },

  onCoursePickerChange(e) {
    const selectedCourseIndex = Number(e.detail.value)
    const selected = this.data.courses[selectedCourseIndex]
    if (!selected) return

    this.setData({
      selectedCourseIndex,
      selectedCourseId: selected.course_id,
      selectedCourseName: selected.course_name,
      rosterStudents: selected.students || [],
    })
  },

  async createCourse() {
    const courseId = (this.data.courseIdInput || '').trim()
    const courseName = (this.data.courseNameInput || '').trim()

    if (!courseId || !courseName) {
      wx.showToast({ title: '请填写课程编号和课程名称', icon: 'none' })
      return
    }

    wx.showLoading({ title: '创建中...', mask: true })
    try {
      await this.requestJson({
        url: `${API_BASE_URL}/api/v1/courses`,
        method: 'POST',
        data: {
          course_id: courseId,
          course_name: courseName,
        },
      })

      this.setData({
        courseIdInput: '',
        courseNameInput: '',
      })

      await this.loadCourses()
      const idx = this.data.courses.findIndex(c => c.course_id === courseId)
      if (idx >= 0) {
        const selected = this.data.courses[idx]
        this.setData({
          selectedCourseIndex: idx,
          selectedCourseId: selected.course_id,
          selectedCourseName: selected.course_name,
          rosterStudents: selected.students || [],
        })
      }
      wx.showToast({ title: '课程创建成功', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '创建课程失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  async addStudent() {
    const courseId = this.data.selectedCourseId
    if (!courseId) {
      wx.showToast({ title: '请先创建或选择课程', icon: 'none' })
      return
    }

    const studentId = (this.data.studentIdInput || '').trim()
    const name = (this.data.studentNameInput || '').trim()
    const className = (this.data.classNameInput || '').trim()

    if (!studentId || !name) {
      wx.showToast({ title: '请填写学号和姓名', icon: 'none' })
      return
    }

    wx.showLoading({ title: '添加中...', mask: true })
    try {
      const roster = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/courses/${courseId}/students`,
        method: 'POST',
        data: {
          student_id: studentId,
          name,
          class_name: className,
        },
      })

      this.setData({
        rosterStudents: roster.students || [],
        studentIdInput: '',
        studentNameInput: '',
        classNameInput: '',
      })

      await this.loadCourses()
      wx.showToast({ title: '学生已添加', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '添加失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  async removeStudent(e) {
    const studentId = e.currentTarget.dataset.sid
    const courseId = this.data.selectedCourseId

    if (!studentId || !courseId) return

    wx.showLoading({ title: '移除中...', mask: true })
    try {
      const roster = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/courses/${courseId}/students/${studentId}`,
        method: 'DELETE',
      })

      this.setData({ rosterStudents: roster.students || [] })
      await this.loadCourses()
      wx.showToast({ title: '已移除', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '移除失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  chooseRosterFile() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['csv', 'xlsx'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file) return
        this.setData({
          importFilePath: file.path,
          importFileName: file.name || '未命名文件',
        })
      },
      fail: (err) => {
        if (err && err.errMsg && err.errMsg.includes('cancel')) return
        wx.showToast({ title: '选择文件失败', icon: 'none' })
      }
    })
  },

  importStudents() {
    const courseId = this.data.selectedCourseId
    const filePath = this.data.importFilePath

    if (!courseId) {
      wx.showToast({ title: '请先创建或选择课程', icon: 'none' })
      return
    }

    if (!filePath) {
      wx.showToast({ title: '请先选择 CSV/XLSX 文件', icon: 'none' })
      return
    }

    wx.showLoading({ title: '导入中...', mask: true })

    wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/courses/${courseId}/students/import`,
      filePath,
      name: 'file',
      success: async (res) => {
        wx.hideLoading()

        if (res.statusCode < 200 || res.statusCode >= 300) {
          let message = `导入失败 (${res.statusCode})`
          try {
            const data = JSON.parse(res.data)
            const detail = data && data.detail
            message = typeof detail === 'string' ? detail : message
          } catch (err) {}
          wx.showToast({ title: message, icon: 'none' })
          return
        }

        try {
          const roster = JSON.parse(res.data)
          this.setData({
            rosterStudents: roster.students || [],
            importFilePath: '',
            importFileName: '',
          })
          await this.loadCourses()
          wx.showToast({ title: '导入成功', icon: 'success' })
        } catch (err) {
          wx.showToast({ title: '导入结果解析失败', icon: 'none' })
        }
      },
      fail: () => {
        wx.hideLoading()
        wx.showToast({ title: '导入请求失败', icon: 'none' })
      }
    })
  },

  // ========== 创建作业 - 模式选择 ==========

  selectAssignmentMode(e) {
    const mode = e.currentTarget.dataset.mode
    this.setData({
      assignmentMode: mode,
      createdAssignment: null,
    })
  },

  resetAssignmentMode() {
    this.setData({
      assignmentMode: null,
      assignmentTitle: '',
      questionContent: '',
      teacherAnswer: '',
      maxScoreInput: '10',
      solveImagePath: '',
      solveImagePreview: '',
      solveSpecifications: '',
      extractedQuestion: null,
      createdAssignment: null,
      // 重置时间配置
      assignmentStartTime: '',
      assignmentEndTime: '',
      assignmentAppealTime: '',
      dateTimeStart: [0, 0, 0, 0, 0],
      dateTimeEnd: [0, 0, 0, 0, 0],
      dateTimeAppeal: [0, 0, 0, 0, 0],
    })
    this.initDateTimePicker()
  },

  createAnotherAssignment() {
    this.setData({
      createdAssignment: null,
      assignmentTitle: '',
      questionContent: '',
      teacherAnswer: '',
      maxScoreInput: '10',
      solveImagePath: '',
      solveImagePreview: '',
      solveSpecifications: '',
      extractedQuestion: null,
      assignmentSubTab: 'create',
    })
  },

  // ========== 时间选择器 ==========

  onStartTimeChange(e) {
    const value = e.detail.value
    const dateStr = this._formatDateTime(value)
    this.setData({
      dateTimeStart: value,
      assignmentStartTime: dateStr
    })
  },

  onEndTimeChange(e) {
    const value = e.detail.value
    const dateStr = this._formatDateTime(value)
    this.setData({
      dateTimeEnd: value,
      assignmentEndTime: dateStr
    })
  },

  onAppealTimeChange(e) {
    const value = e.detail.value
    const dateStr = this._formatDateTime(value)
    this.setData({
      dateTimeAppeal: value,
      assignmentAppealTime: dateStr
    })
  },

  _formatDateTime(arr) {
    if (!this.data.dateTimeArray) return ''
    const y = this.data.dateTimeArray[0][arr[0]]
    const m = this.data.dateTimeArray[1][arr[1]]
    const d = this.data.dateTimeArray[2][arr[2]]
    const h = this.data.dateTimeArray[3][arr[3]]
    const min = this.data.dateTimeArray[4][arr[4]]
    return `${y}-${m}-${d} ${h}:${min}`
  },

  // ========== 规则配置 ==========

  onAllowResubmitChange(e) {
    this.setData({ allowResubmit: e.detail.value })
  },

  onAllowLateChange(e) {
    this.setData({ allowLate: e.detail.value })
  },

  onLateRuleChange(e) {
    this.setData({ lateRuleIndex: e.detail.value })
  },

  // ========== 创建作业 - 手动输入模式 ==========

  async createAssignmentManual() {
    const title = (this.data.assignmentTitle || '').trim()
    const questionContent = (this.data.questionContent || '').trim()
    const teacherAnswer = (this.data.teacherAnswer || '').trim()
    const maxScore = Number(this.data.maxScoreInput)

    if (!title || !questionContent || !teacherAnswer) {
      wx.showToast({ title: '请完整填写作业信息', icon: 'none' })
      return
    }

    if (!Number.isFinite(maxScore) || maxScore <= 0) {
      wx.showToast({ title: '满分必须是大于 0 的数字', icon: 'none' })
      return
    }

    wx.showLoading({ title: '创建中...', mask: true })

    try {
      const assignment = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments`,
        method: 'POST',
        data: {
          title,
          questions: [
            {
              type: 'text',
              content: questionContent,
              max_score: maxScore,
            }
          ],
          submit_start_time: this.data.assignmentStartTime,
          submit_end_time: this.data.assignmentEndTime,
          appeal_end_time: this.data.assignmentAppealTime,
          allow_resubmit: this.data.allowResubmit,
          allow_late: this.data.allowLate,
          late_score_rule: this.data.lateRuleValues[this.data.lateRuleIndex],
        }
      })

      await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${assignment.id}/answers/teacher-submit`,
        method: 'POST',
        data: {
          answers: [
            {
              question_index: 0,
              answer: teacherAnswer,
            }
          ]
        }
      })

      this.setData({
        createdAssignment: {
          id: assignment.id,
          title: assignment.title,
        },
        assignmentSubTab: 'list',
      })

      wx.showToast({ title: '作业创建成功', icon: 'success' })
      this.loadAssignments()
    } catch (err) {
      wx.showToast({ title: err.message || '创建作业失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  // ========== 创建作业 - 拍照上传模式 ==========

  chooseSolveImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles[0]
        if (!file) return
        this.setData({
          solveImagePath: file.tempFilePath,
          solveImagePreview: file.tempFilePath,
          extractedQuestion: null,
        })
      },
      fail: (err) => {
        if (err && err.errMsg && err.errMsg.includes('cancel')) return
        wx.showToast({ title: '选择图片失败', icon: 'none' })
      }
    })
  },

  onSolveSpecInput(e) {
    this.setData({ solveSpecifications: e.detail.value })
  },

  // 识别题目并提取
  async solveAndExtractQuestion() {
    const { solveImagePath, solveSpecifications } = this.data

    if (!solveImagePath) {
      wx.showToast({ title: '请先选择题目图片', icon: 'none' })
      return
    }

    if (!solveSpecifications.trim()) {
      wx.showToast({ title: '请输入题目指定', icon: 'none' })
      return
    }

    this.setData({ solveLoading: true })

    wx.uploadFile({
      url: `${API_BASE_URL}/api/v1/solve/upload`,
      filePath: solveImagePath,
      name: 'file',
      formData: {
        specifications: solveSpecifications.trim()
      },
      success: (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          let message = `识别失败 (${res.statusCode})`
          try {
            const data = JSON.parse(res.data)
            const detail = data && data.detail
            message = typeof detail === 'string' ? detail : (detail && detail.message) || message
          } catch (err) {}
          wx.showToast({ title: message, icon: 'none', duration: 3000 })
          this.setData({ solveLoading: false })
          return
        }

        try {
          const result = JSON.parse(res.data)
          const questions = result.specified_questions || []

          if (!questions.length || !questions[0].found) {
            wx.showToast({ title: '未找到指定题目，请检查指定格式', icon: 'none' })
            this.setData({ solveLoading: false })
            return
          }

          const q = questions[0]
          // 预处理可编辑数据
          const extractedQuestion = {
            specification: q.specification,
            content: q.content || '',
            full_solution: q.full_solution || '',
            question_type: q.question_type || '',
            difficulty: q.difficulty || '',
            knowledge_points: q.knowledge_points || [],
            knowledge_points_str: (q.knowledge_points || []).join('、'),
            max_score: 10,
          }

          this.setData({
            extractedQuestion,
            solveLoading: false,
          })

          wx.showToast({ title: '识别成功，请核对修改', icon: 'success' })
        } catch (err) {
          wx.showToast({ title: '解析结果失败', icon: 'none' })
          this.setData({ solveLoading: false })
        }
      },
      fail: () => {
        wx.showToast({ title: '请求失败', icon: 'none' })
        this.setData({ solveLoading: false })
      }
    })
  },

  // 编辑识别结果的字段
  onExtractedFieldInput(e) {
    const key = e.currentTarget.dataset.key
    if (!key || !this.data.extractedQuestion) return

    const value = e.detail.value
    this.setData({
      [`extractedQuestion.${key === 'extractedContent' ? 'content' : key === 'extractedAnswer' ? 'full_solution' : key === 'extractedMaxScore' ? 'max_score' : key}`]: value
    })
  },

  // 从拍照结果创建作业
  async createAssignmentFromPhoto() {
    const { assignmentTitle, extractedQuestion } = this.data
    const title = (assignmentTitle || '').trim()

    if (!title) {
      wx.showToast({ title: '请填写作业标题', icon: 'none' })
      return
    }

    if (!extractedQuestion || !extractedQuestion.content) {
      wx.showToast({ title: '题目内容不能为空', icon: 'none' })
      return
    }

    const maxScore = Number(extractedQuestion.max_score)
    if (!Number.isFinite(maxScore) || maxScore <= 0) {
      wx.showToast({ title: '满分必须是大于0的数字', icon: 'none' })
      return
    }

    wx.showLoading({ title: '创建中...', mask: true })

    try {
      const assignment = await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments`,
        method: 'POST',
        data: {
          title,
          questions: [
            {
              type: 'text',
              content: extractedQuestion.content,
              max_score: maxScore,
            }
          ],
          submit_start_time: this.data.assignmentStartTime,
          submit_end_time: this.data.assignmentEndTime,
          appeal_end_time: this.data.assignmentAppealTime,
          allow_resubmit: this.data.allowResubmit,
          allow_late: this.data.allowLate,
          late_score_rule: this.data.lateRuleValues[this.data.lateRuleIndex],
        }
      })

      await this.requestJson({
        url: `${API_BASE_URL}/api/v1/assignments/${assignment.id}/answers/teacher-submit`,
        method: 'POST',
        data: {
          answers: [
            {
              question_index: 0,
              answer: extractedQuestion.full_solution || '暂无答案',
            }
          ]
        }
      })

      this.setData({
        createdAssignment: {
          id: assignment.id,
          title: assignment.title,
        },
        assignmentSubTab: 'list',
      })

      wx.showToast({ title: '作业创建成功', icon: 'success' })
      this.loadAssignments()
    } catch (err) {
      wx.showToast({ title: err.message || '创建作业失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  copyAssignmentId() {
    const assignment = this.data.createdAssignment
    if (!assignment || !assignment.id) return

    wx.setClipboardData({
      data: assignment.id,
      success: () => wx.showToast({ title: '作业ID已复制', icon: 'success' }),
    })
  },

  // ========== 通用请求方法 ==========

  requestJson({ url, method = 'GET', data = null, header = {} }) {
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
        fail: () => reject(new Error('网络请求失败，请检查后端服务')),
      })
    })
  },
})
