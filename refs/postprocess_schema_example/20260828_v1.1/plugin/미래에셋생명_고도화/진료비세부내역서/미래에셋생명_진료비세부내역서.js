"use strict"

const { Logger } = require("/usr/src/app/dist/apps/extn/libs/common/src/logger");

// const pluginUtilCache = require.resolve("./pluginUtil_세부.js");
const pluginUtilCache = require.resolve("./pluginUtil_세부_test.js");
delete require.cache[pluginUtilCache];
const pluginUtil = require(pluginUtilCache);

const formatCache = require.resolve("./format_세부.js");
delete require.cache[formatCache];
const format = require(formatCache);

const path = require("path");
const fs = require("fs");
const fsPromises = require('fs/promises');
const xlsx = require("xlsx");
const excelPath = path.join("/data/data/excel");

/**
 * plugin
 * @param {extractionResultData}
 * extractionResultData Property
 *  modelmapdata : Object // 모델 결과 map(연결정보 및 여러거자 정보 보유)  
 *  allcontents : string // ocr 인식 결과를 하나의 string으로 연결한 값     
 *  result : Array<Object> // schema 추출 결과값  
 *  extraData : undefined | any // plugin에서 추가 정보를 최종결과에 전달 가능한 속성   
 * @param {schemaObj}
 * schemaObj는 추출에 사용한 schema 객체
 * @returns
 * extractionResultData와 같은 형태로 반환해야 한다.
 */

// const logger = new Logger();

exports.plugin = function (extractionResultData, schemaObj) {
  // Logger.log("test")
  // Logger.debug("test")

  Logger.debug(`#################### ${extractionResultData?.modelmapdata?.category} Plugin START \t ${extractionResultData.modelmapdata.fileNm} ####################`);
  let values = extractionResultData?.result;
  let arrtcd = pluginUtil.getArrtcd(extractionResultData?.modelmapdata);
  let category = extractionResultData?.modelmapdata?.category;

  // 추출항목 정의
  let keyObj = pluginUtil.readKeyList(__dirname + "/항목리스트.json", extractionResultData?.modelmapdata?.category);
  Logger.log(extractionResultData?.modelmapdata?.category)
  //===========================================================
  // 표데이터에서 표가 2개인데 첫번째 표엔 타이틀만 있고 값은 없을때 제거
  values?.forEach((value) => {
    value?.data?.forEach((data) => {
      data?.values?.forEach((v) => {
        const seen = new Set();
        v.relativeValueInfo = v.relativeValueInfo?.filter((r) => {
          const key = `${r.keyLabels?.[0]}|${r.index}|${r.label}`;
          if (seen.has(key)) {
            return false; // 이미 존재하면 제거
          }
          seen.add(key);
          return true; // 처음 본 조합이면 유지
        });
      });
    });
  });
  //===========================================================

  //===========================================================
  values?.forEach((value, valueIdx) => {
    value?.data?.forEach((data) => {
      const seen = new Set();
      value.data = value.data?.filter(item => {
        if (seen.has(item.detectedIndex)) {
          return false;
        }
        seen.add(item.detectedIndex);
        return true;
      });
      data?.values?.forEach((v) => {
        v?.relativeValueInfo?.forEach((r) => {
          if (r.keyLabels[0] === "구분(외래)") {
            r.label = r.label.replace(/[0-9\\.\\,]/g, "")
            r.label = r.label.replace(/(--)/g, "")
          }
          if (r.keyLabels[1] === "본인부담총액") {
            r.keyLabels[1] = "비급여"
          }
        });
      });
      if (value.name == "표데이터") {
        data?.values?.forEach((v) => {
          v?.relativeValueInfo?.forEach((r) => {
            if (r.keyLabels[0] == "기타") {
              let originkeyLabel = r.keyLabels[0];
              r.keyLabels[0] = r.header;
            }
            else if (r.keyLabels[0] == "코드EDI") {
              r.keyLabels[0] = "EDI코드";
            }
          })
        })
      }
    });
  });
  //==========================================================

  //====================== 병실 > 비고 start ====================
  //병실에 외래 >> 비고란에 외래
  //병실에 입원 or 호실이 적혀있으면 비고란에 입원 
  let roomLabel = "";
  let remarkLabel = "";
  // 병실 cont 찾기
  values?.forEach((value) => {
    if (value?.name !== "환자정보(병실)") return;


    value?.data?.forEach((data) => {
      data?.values?.forEach((v) => {
        roomLabel = (v?.label ?? "").toString().trim();
      });
    });

    // 변환값 생성
    // 병실 패턴
    const roomPattern = /^(?=.*\d)[A-Za-z0-9/:-]+(호)?$/i;
    function getRemarkLabel(roomLabel) {
      if (roomLabel === "외래") return "통원";
      if (roomLabel.includes("입원")) return "입원";
      if (roomPattern.test(roomLabel)) return "입원";
      return "";
    }
    remarkLabel = getRemarkLabel(roomLabel);
    // console.log(">>>>", remarkLabel)

    //비고 반영 
    values?.forEach((value2) => {
      if (value2?.name !== "환자정보(입통원구분)") return;

      let wrote = false;
      value2?.data?.forEach((data2) => {
        if (data2.values.length === 0) {
          data2.values.push(
            {
              cellType: 'cell',
              label: remarkLabel,
              index: 19,
              relativeLabelsInfo: [],
              relativeValueInfo: [],
              confidence: 1,
              coordinates: [],
              ocrInfo: []
            }
          );
        }
        data2?.values?.forEach((v2) => {
          if (!wrote) {
            v2.label = remarkLabel;
            wrote = true;
          } else {
            v2.label = "";
          }
          // console.log("################", v2.label)
        });
      });
    });
  });
  //====================== 병실 > 비고 end ======================

  //====================== 진료기간 start =======================
  let treatmenPeriod = "";
  values?.forEach((value) => {
    if (!value?.name?.includes("진료기간")) return;
    value?.data?.forEach((data) => {
      data?.values?.forEach((v) => {
        treatmenPeriod = (v?.label ?? "").toString().trim();
      });
    });
  });

  // 진료시작일 종료일 분리
  let startDate = "";
  let endDate = "";

  const period = (treatmenPeriod || "").trim();
  const dateRegex = /(?:\d{4}[-./]\d{2}[-./]\d{2}|\d{8}|\d{2}[-./]\d{2}[-./]\d{2})/g;

  function normalizeDate(dateStr) {
    if (!dateStr) return "";

    //23-01-01
    if (/^\d{2}[-./]\d{2}[-./]\d{2}$/.test(dateStr)) {
      const cleaned = dateStr.replace(/[-./]/g, "");
      return "20" + cleaned; // -> 20230131
    }
    //2023-01-31
    if (/^\d{4}[-./]\d{2}[-./]\d{2}$/.test(dateStr)) {
      return dateStr.replace(/[-./]/g, "");
    }
    //20230131은 그대로
    if (/^\d{8}$/.test(dateStr)) {
      return dateStr;
    }
    return "";
  }

  const matches = period.match(dateRegex) || [];
  // console.log("###########",matches)

  startDate = normalizeDate(matches[0] ?? "");
  endDate = normalizeDate(matches[1] ?? "");

  if (startDate && !endDate) endDate = startDate;
  if (/~/.test(period)) {
    const parts = period.split(/\s*~\s*/);

    const s = parts[0]?.match(dateRegex)?.[0];
    const e = parts[1]?.match(dateRegex)?.[0];

    if (s) startDate = normalizeDate(s);
    if (e) endDate = normalizeDate(e);

    if (startDate && !endDate) endDate = startDate;
  }
  // 첫번째 값만 가져오는거 2020010209415405 때문에 수정
  values?.forEach((value) => {
    if (value?.name === "진료기간(진료시작일)") {
      value?.data?.forEach((data) => {
        if (!Array.isArray(data?.values) || data.values.length === 0) return;

        //첫번째값만 가져오기
        data.values = [data.values[0]];
        data.values[0].label = startDate;
      });
    }
    if (value?.name === "진료기간(진료종료일)") {
      value?.data?.forEach((data) => {
        if (!Array.isArray(data?.values) || data.values.length === 0) return;

        //첫번째값만 가져오기
        data.values = [data.values[0]];
        data.values[0].label = endDate;
      });
    }
  });
  // console.log("@@@@@@@@@@@@@@@@@", startDate, endDate)
  //====================== 진료기간 end =======================

  //합계 값 없으면 0
  values?.forEach((value) => {
    if (value?.name !== "합계") return;
    // if (value?.name == "표데이터") return;

    // const template = value?.data?.flatMap((data) => Array.isArray(data?.values) ? data.values : [])?.find((v) => v && typeof v === "object");
    // console.log(template)
    value?.data?.forEach((data) => {
      // if (!Array.isArray(data.values) || data.values.length === 0) {
      //   data.values = [
      //     {
      //       label: "0",
      //     },
      //   ];
      //   return;
      // }

      data?.values?.forEach((v) => {
        if (v?.label === undefined || v?.label === null || String(v.label).trim() === "") {
          v.label = "0";
        }
      })
    })
  });


  //  values?.forEach((value) => {
  //   console.log("@@@@", value?.name)
  //   if (value?.name !=="비급여") return;
  //   console.log("@@@@@", value?.name);
  //  });



  // 결과 구조 변경
  values = format.setResultFormat(values, keyObj, arrtcd, extractionResultData?.modelmapdata?.category);

  const test1 = values?.find(item => item?.img_extc_itnm === "본인부담")?.extc_rst_seq || 2;
  const test2 = values?.find(item => item?.img_extc_itnm === "공단부담")?.extc_rst_seq || 3;
  const test3 = values?.find(item => item?.img_extc_itnm === "전액본인부담")?.extc_rst_seq || 4;
  const test4 = values?.find(item => item?.img_extc_itnm === "총액")?.extc_rst_seq || 1;
  const test5 = values?.find(item => item?.img_extc_itnm === "비급여")?.extc_rst_seq || 5;

  const seqMap = {};
  values?.forEach((v) => {
    if (v.chartNm !== '표데이터') return;

    const key = v.extc_itm_no;

    if (key === undefined || key === null) {
      v.extc_rst_seq = 0;
      return;
    }

    if (!seqMap[key]) {
      seqMap[key] = 1;
    } else {
      seqMap[key] += 1;
    }
    v.extc_rst_seq = seqMap[key]
  });

  //============================================ extc_rst_cont09 값 넣기 =========================================
  values.forEach((v) => {
    if (v.img_extc_itnm?.includes('본인부담') && !v.img_extc_itnm?.includes('전액')) {
      v.extc_rst_cont09 = '일부본인부담';
      v.extc_itm_tpvl = '급여';
      v.extc_rst_seq = test1;
      v.lvl_no = 3;
    }
    else if (v.img_extc_itnm?.includes('공단부담')) {
      v.extc_rst_cont09 = '일부공단부담';
      v.extc_itm_tpvl = '급여';
      v.extc_rst_seq = test2;
      v.lvl_no = 3;
    }
    //전액본인부담에 값이 없을경우가 있음
    else if (v.img_extc_itnm?.includes('전액본인부담')) {
      v.extc_rst_cont09 = '전액본인부담';
      v.extc_itm_tpvl = '급여';
      v.lvl_no = 2;
      v.extc_rst_seq = test3;
    }
  });
  //============================================ extc_rst_cont09 값 넣기 =========================================

  //===================================== img_extc_itnm 명칭 맞추기 ===============================================
  values?.forEach((v) => {
    if (v?.img_extc_itnm === '코드') v.img_extc_itnm = 'EDI코드';
    if (v?.img_extc_itnm === '명칭') v.img_extc_itnm = 'EDI명칭';
    if (v?.img_extc_itnm === '금액') v.img_extc_itnm = '단가';
    if (v?.img_extc_itnm?.includes("급여_") && !v?.img_extc_itnm?.includes("총액")) v.img_extc_itnm = v.img_extc_itnm + '총액';
    if (v?.img_extc_itnm === '급여_비급여총액') {
      v.img_extc_itnm = '비급여총액';
      v.extc_rst_seq = test5;
    }
    if (v?.img_extc_itnm === '급여_총액') {
      v.img_extc_itnm = '총액합계';
      v.extc_rst_seq = test4;
    }
    if (v?.img_extc_itnm === '급여_선택진료총액') v.img_extc_itnm = '선택진료총액';
  });
  //===================================== img_extc_itnm 명칭 맞추기 ===============================================

  // ===================================== 급여구분 START =====================================

  const groupMap = new Map();

  (values || []).forEach(v => {
    if (v?.chartNm && v.chartNm !== '표데이터') return;

    const key = v?.extc_itm_no;
    if (key == null) return;

    if (!groupMap.has(key)) groupMap.set(key, []);
    groupMap.get(key).push(v);
  });

  for (const rows of groupMap.values()) {
    let payType = null;
    let amount = null;
    let totalamount = null;
    let payRow = null;
    let nonPayRow = null;

    rows.forEach(v => {
      const name = (v?.img_extc_itnm ?? "").trim();
      const val = (v?.extc_rst_cont01 ?? "").toString().trim();

      if (name === "급여구분") payType = val;

      if (name === "단가") amount = val;
      if (name === "총액") totalamount = val;

      if (name === "급여") payRow = v;
      if (name === "비급여") nonPayRow = v;
    });

    let finalAmount = null;

    if (totalamount) finalAmount = totalamount;
    else if (amount) finalAmount = amount;

    if (!finalAmount) continue;

    if (payType === "급여" && payRow) {
      payRow.extc_rst_cont01 = finalAmount.replace(/[,]/g, "");
    }
    if (payType === "비급여" || payType === "비급" && nonPayRow) {
      nonPayRow.extc_rst_cont01 = finalAmount.replace(/[,]/g, "");
    }
  }

  // =================================== 표데이터면 table-contents / 아니면 header-contents 넣기 START ===================
  values.forEach((v) => {
    if (v.chartNm === '표데이터') {
      const base = v.extc_rst_cont10 ?? '';

      if (!base.includes('table-contents')) {
        v.extc_rst_cont10 = base
          ? `${base} table-contents`
          : 'table-contents';
      }
    } else {
      v.extc_rst_cont10 = 'header-contents'
    }
  });
  // =================================== 표데이터면 table-contents / 아니면 header-contents 넣기 END ===================

  //일자 없는 경우
  let d = "";
  values?.forEach((v) => {
    // console.log("##",startDate, endDate)
    if (v.img_extc_itnm === "진료기간(진료시작일)" && v.extc_rst_cont01) {
      d = v.extc_rst_cont01;
    }
    if (
      v.img_extc_itnm === "일자" &&
      (!v.extc_rst_cont01 || v.extc_rst_cont01 === "")
    ) {
      v.extc_rst_cont01 = startDate + endDate;
    }
    //진료기간 년도 가져와서 붙힘
    else if (v.img_extc_itnm === "일자" && /^\d{4}$/.test(v.extc_rst_cont01)) {
      v.extc_rst_cont01 = d.slice(0, 4) + v.extc_rst_cont01;
    }
  });

  values.forEach((v) => {
    // Logger.log(v.extrtId, "===> ", v.extrtItmNm)
    if (v.img_extc_itnm == "일부본인부담금비급여" || v.img_extc_itnm == "현금영수증") {
      if (v.extc_rst_cont01 == "00") {
        v.extc_rst_cont01 = 0
      }
    }
    // Logger.log(v)
    if (typeof v?.extc_rst_cont01 === 'string' && v?.extc_rst_cont01?.includes("[UNK]")) {
      v.extc_rst_cont01 = v?.extc_rst_cont01.replace("[UNK]", "")
    }
  });

  // ============================= 일자 from to 추가하기 START ===================================
  let startendDate = "";
  let itmValCoordVal = "";
  values?.forEach((v) => {
    if (v.img_extc_itnm === "일자") {
      startendDate = v.extc_rst_cont01;
      itmValCoordVal = v.extc_rst_img_crdn_vl;
    }
    if (v.img_extc_itnm === "시작일자" || v.img_extc_itnm === "종료일자") {
      v.extc_rst_cont01 = startendDate;
      v.extc_rst_img_crdn_vl = itmValCoordVal;
    }
    // console.log(startendDate, itmValCoordVal)
    if (v.img_extc_itnm === "일자" || v.img_extc_itnm === "시작일자" || v.img_extc_itnm === "종료일자") {
      if (!v.extc_rst_cont01) return;
      const raw = v.extc_rst_cont01.toString().trim();
      // console.log("@@@@RAW@@@@",raw)

      const isValidDate = (yyyymmdd) => {
        if (!/^\d{8}/.test(yyyymmdd)) return false;

        const y = Number(yyyymmdd.slice(0, 4));
        const m = Number(yyyymmdd.slice(4, 6));
        const d = Number(yyyymmdd.slice(6, 8));

        if (m < 1 || m > 12) return false;
        if (d < 1 || d > 31) return false;

        const dt = new Date(y, m - 1, d);
        return (
          dt.getFullYear() === y &&
          dt.getMonth() === m - 1 &&
          dt.getDate() === d
        );
      };
      //16자리일대 from to
      if (/^\d{16}$/.test(raw)) {
        const from = raw.slice(0, 8);
        const to = raw.slice(8, 16);
        // Logger.log(`날짜 16자리 일때`, from, to)
        if (isValidDate(from) || isValidDate(to)) {
          if (v.img_extc_itnm === '시작일자') v.extc_rst_cont01 = from;
          if (v.img_extc_itnm === '종료일자') v.extc_rst_cont01 = to;
          if (v.img_extc_itnm === '일자') v.extc_rst_cont01 = `${from}${to}`;
          return;
        }
      }

      //8자리일때 앞에 from
      if (/^\d{8}$/.test(raw)) {
        // console.log(`날짜 8자리 일때`, raw)
        if (isValidDate(raw)) {
          if (v.img_extc_itnm === '시작일자') v.extc_rst_cont01 = raw;
          if (v.img_extc_itnm === '종료일자') v.extc_rst_cont01 = raw;
          if (v.img_extc_itnm === '일자') v.extc_rst_cont01 = `${raw}${raw}`;
          return;
        }
      }

      if (/^\d{12}$/.test(raw)) {
        // console.log(`날짜 12자리 일때`, v.extc_rst_cont01)
        const from = raw.slice(0, 8);
        const to = raw.slice(0, 4) + raw.slice(8, 12);

        if (isValidDate(from) || isValidDate(to)) {
          if (v.img_extc_itnm === '시작일자') v.extc_rst_cont01 = from;
          if (v.img_extc_itnm === '종료일자') v.extc_rst_cont01 = to;
          if (v.img_extc_itnm === '일자') v.extc_rst_cont01 = `${from}${to}`;
          return;
        }
      }
    }
  });
  // ============================= 일자 from to 추가하기 END ===================================


  // ==================== 횟수 X 추가 START =========================
  values?.forEach((v) => {
    if (v.img_extc_itnm !== "횟수") return;

    const str = v.extc_rst_cont01.replace(",", '').toString().replace(/\s/g, '');

    const match = str.match(/^(\d+(?:\.\d+)?)(x|\*)(\d+(?:\.\d+)?)$/, '');

    if (!match) return;

    if (match) {
      const num1 = parseFloat(match[1]);
      const num2 = parseFloat(match[3]);
      v.extc_rst_cont01 = String(num1 * num2);
    }
  })
  // ==================== 횟수 X 추가 END   =========================

  // ==================== 사고발생일자 추가 START =======================
  const startItem = values.find(v => v.img_extc_itnm === "진료기간(진료시작일)");
  const startVal = startItem?.extc_rst_cont01 || "";

  values.forEach(v => {
    v.acd_ogtdt = startVal;
  });
  // ==================== 사고발생일자 추가 END =========================

  values?.forEach((v) => {
    if (v.img_extc_itnm === "횟수") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, ".").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "투여량") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, ".").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "비급여") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "전액본인부담") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "본인부담") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "공단부담") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "단가") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "선택진료이외총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "급여_본인부담총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "급여_공단부담총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "급여_전액본인부담총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "비급여총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "급여_급여총액") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
    if (v.img_extc_itnm === "총액합계") v.extc_rst_cont01 = v.extc_rst_cont01.replace(/[,]/g, "").replace(/[oOㅇ이]/g, '0').replace(/[^0-9.\\-]/g, '');
  });

  if (!Array.isArray(values)) {
    values = [];
  }

  //합계값 없을 때 '0' 넣기
  const targetItems = [
    "급여_본인부담총액",
    "급여_공단부담총액",
    "급여_전액본인부담총액",
    "비급여총액",
    "총액합계"
  ];

  const existingTotal = values.find((v) => targetItems.includes(v?.img_extc_itnm));
  let totalItmNo;
  if (existingTotal?.extc_itm_no != null) {
    totalItmNo = existingTotal.extc_itm_no;
  } else {
    const lastItem = [...values].reverse().find((v) => v?.img_extc_itnm === "항목");

    totalItmNo = Number(lastItem?.extc_itm_no ?? 0) + 1;
  }

  targetItems.forEach((itemName) => {
    const exists = values.some((v) => {
      return v?.img_extc_itnm === itemName
    });

    if (exists) return;

    const seqMap = {
      "급여_본인부담총액": test1,
      "급여_공단부담총액": test2,
      "급여_전액본인부담총액": test3,
      "비급여총액": test5,
      "총액합계": test4
    }

    const seqMap2 = {
      "급여_본인부담총액": "일부본인부담",
      "급여_공단부담총액": "일부공단부담",
      "급여_전액본인부담총액": "전액본인부담",
      "비급여총액": '',
      "총액합계": ''
    }

    values.push({
      img_extc_itnm: itemName,
      extc_rst_cont01: "0",
      extc_itm_no: totalItmNo,
      extc_rst_seq: seqMap[itemName],
      lvl_no: 1,
      hgrk_extc_itm_no: 0,
      extc_itm_tpvl: "급여",
      extc_rst_cont09: seqMap2[itemName],
      extc_rst_cont10: "table-contents",
      acd_ogtdt: startVal,
      self_rlbtr_vl:1,
      extc_rst_img_crdn_vl:[]
    });

  });


  //각종제거
  values = values.filter(v => v.img_extc_itnm !== '일자');
  values = values.filter(v => v.img_extc_itnm !== '전화번호');
  values = values.filter(v => v.img_extc_itnm !== '계');

  values = values.filter(v => {
    if (!v?.img_extc_itnm?.startsWith('급여_')) return true;

    const val = v?.extc_rst_cont01;

    if (
      val === null ||
      val === undefined ||
      val === '' ||
      (typeof val === 'string' && val.trim() === '')
    ) {
      return false;
    }
    return true;
  })
  // Logger.log(values)
  extractionResultData.extraData = values;
  extractionResultData.result = values;
  // pluginUtil.saveValuesCountToExcel(
  //   extractionResultData?.modelmapdata?.category,
  //   extractionResultData?.modelmapdata?.fileNm,
  //   values.length
  // );

  // 로그 출력
  // pluginUtil.printResultLog('', values);
  // console.log("3333333333333",JSON.stringify(values,null,2))
  // pluginUtil.printResultLogExcel('excel', values, extractionResultData, keyObj);

  Logger.debug(`#################### ${extractionResultData?.modelmapdata?.category} Plugin END #################### \t ${extractionResultData.modelmapdata.fileNm}`);

  return extractionResultData;
};

