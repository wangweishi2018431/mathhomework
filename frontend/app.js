// app.js
const STUDENT_PROFILE_KEY = 'student_profile'

App({
  onLaunch() {
    console.log('AI数学作业批改小程序启动')

    try {
      const cachedProfile = wx.getStorageSync(STUDENT_PROFILE_KEY)
      if (cachedProfile && cachedProfile.nickName) {
        this.globalData.studentProfile = cachedProfile
      }
    } catch (err) {
      console.warn('读取本地登录态失败:', err)
    }
  },

  globalData: {
    // 本地开发后端地址
    apiBaseUrl: 'http://127.0.0.1:18080',
    studentProfile: null,
  }
})
