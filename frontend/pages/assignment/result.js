const app = getApp()

Page({
  data: {
    result: null,
  },

  onLoad() {
    // 从全局获取结果数据
    const resultData = app.globalData?.lastResult
    if (resultData) {
      this.setData({ result: resultData })
    } else {
      wx.showToast({
        title: '未找到批改结果',
        icon: 'none',
      })
    }
  },

  goBack() {
    wx.navigateBack()
  },
})
