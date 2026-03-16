/**
 * 微信云存储工具函数
 * 用于图片上传到腾讯云存储(COS)
 */

const app = getApp()

/**
 * 选择图片并上传到云存储
 * @param {Object} options - 配置选项
 * @param {number} options.count - 最多选择图片数量，默认 1
 * @param {string} options.sourceType - 图片来源，可选 'album'(相册) | 'camera'(相机) | ['album', 'camera']
 * @returns {Promise<{fileID: string, tempFilePath: string}>}
 */
function chooseAndUploadImage(options = {}) {
  const { count = 1, sourceType = ['album', 'camera'] } = options

  return new Promise((resolve, reject) => {
    // 1. 选择图片
    wx.chooseMedia({
      count,
      mediaType: ['image'],
      sourceType,
      success: (res) => {
        const tempFilePath = res.tempFiles[0].tempFilePath

        // 2. 上传到云存储
        uploadToCloudStorage(tempFilePath)
          .then(fileID => {
            resolve({
              fileID,
              tempFilePath
            })
          })
          .catch(reject)
      },
      fail: reject
    })
  })
}

/**
 * 上传本地图片到云存储
 * @param {string} filePath - 本地临时文件路径
 * @param {string} dir - 云存储目录，默认 'homework'
 * @returns {Promise<string>} fileID - 云文件ID
 */
function uploadToCloudStorage(filePath, dir = 'homework') {
  return new Promise((resolve, reject) => {
    // 生成唯一文件名
    const timestamp = Date.now()
    const randomStr = Math.random().toString(36).substring(2, 8)
    const ext = filePath.match(/\.[^.]+$/) ? filePath.match(/\.[^.]+$/)[0] : '.jpg'
    const cloudPath = `${dir}/${timestamp}_${randomStr}${ext}`

    wx.cloud.uploadFile({
      cloudPath,
      filePath,
      success: (res) => {
        console.log('[CloudStorage] 上传成功:', res.fileID)
        resolve(res.fileID)
      },
      fail: (err) => {
        console.error('[CloudStorage] 上传失败:', err)
        reject(err)
      }
    })
  })
}

/**
 * 获取云存储文件的临时访问链接
 * @param {string} fileID - 云文件ID
 * @returns {Promise<string>} tempFileURL - 临时访问链接
 */
function getTempFileURL(fileID) {
  return new Promise((resolve, reject) => {
    wx.cloud.getTempFileURL({
      fileList: [fileID],
      success: (res) => {
        if (res.fileList && res.fileList[0] && res.fileList[0].tempFileURL) {
          resolve(res.fileList[0].tempFileURL)
        } else {
          reject(new Error('获取临时链接失败'))
        }
      },
      fail: reject
    })
  })
}

/**
 * 删除云存储文件
 * @param {string|Array<string>} fileIDs - 要删除的文件ID
 * @returns {Promise}
 */
function deleteFiles(fileIDs) {
  const ids = Array.isArray(fileIDs) ? fileIDs : [fileIDs]

  return new Promise((resolve, reject) => {
    wx.cloud.deleteFile({
      fileList: ids,
      success: resolve,
      fail: reject
    })
  })
}

/**
 * 统一的图片上传方法（兼容本地开发和云托管）
 * 根据 app.globalData.useCloudStorage 自动选择上传方式
 * @param {string} tempFilePath - 本地临时文件路径
 * @returns {Promise<{url: string, isCloud: boolean}>}
 */
async function uploadImage(tempFilePath) {
  const useCloud = app.globalData.useCloudStorage

  if (useCloud) {
    // 云托管环境：上传到云存储
    try {
      const fileID = await uploadToCloudStorage(tempFilePath)
      const tempURL = await getTempFileURL(fileID)
      return {
        url: tempURL,
        isCloud: true,
        fileID: fileID
      }
    } catch (err) {
      console.error('[Upload] 云存储上传失败，回退到本地:', err)
      // 失败时回退到传统上传方式
    }
  }

  // 本地开发环境：返回临时路径，通过 wx.uploadFile 上传到后端
  return {
    url: tempFilePath,
    isCloud: false
  }
}

module.exports = {
  chooseAndUploadImage,
  uploadToCloudStorage,
  getTempFileURL,
  deleteFiles,
  uploadImage
}
