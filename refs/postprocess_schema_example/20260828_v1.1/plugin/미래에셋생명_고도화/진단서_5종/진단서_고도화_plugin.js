"use strict"

const { Logger } = require("/usr/src/app/dist/apps/extn/libs/common/src/logger");

const pluginUtilCache = require.resolve("./pluginUtil_진단서5종.js");
delete require.cache[pluginUtilCache];
const pluginUtil = require(pluginUtilCache);

const formatCache = require.resolve("./format_진단서5종.js");
delete require.cache[formatCache];
const format = require(formatCache);

const path = require("path");
const fs = require("fs");
const fsPromises = require('fs/promises');
const xlsx = require("xlsx");
const excelPath = path.join("/data/data/excel");

// LLM Service
const llmOpinion = require("../../llm/plugin_llm_진단서_5종.js")
const llmDiseaseName = require("../../llm/plugin_llm_병명코드.js")

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

exports.plugin = async function (extractionResultData, schemaObj) {

  Logger.debug(`#################### ${extractionResultData?.modelmapdata?.category} Plugin START \t ${extractionResultData.modelmapdata.fileNm} ####################`);
  let values = extractionResultData?.result;
  let arrtcd = pluginUtil.getArrtcd(extractionResultData?.modelmapdata);
  let allText = extractionResultData?.allcontents;

  // 추출항목 정의
  let keyObj = pluginUtil.readKeyList(__dirname + "/항목리스트.json", extractionResultData?.modelmapdata?.category);
  // [2025-04-16] '병명' 모델 결과 반영 및 가공
  let diagValue = "";
  let diagName = values?.filter((v) => v?.name == "병명" && v?.data?.length > 0);
  if (diagName?.length > 0) {
    let diag = diagName[0]?.data?.map((d) => d?.values?.map((v => arrtcd[v?.index])));
    if (diag !== undefined) {
      // if(diag[0]?.length > 0) {diagValue = diag?.[0]?.[diag[0]?.length-1]?.mergetext ?? "";
      if (diag?.length > 0) {
        // diagValue = diag[diag?.length-1][0]?.mergetext ?? "";
        diag[0]?.forEach((d) => {
          if (diagValue !== d?.mergetext && d?.mergetext !== undefined) diagValue = diagValue + d?.mergetext;
        });
      }
    }
  }

  let diagPeriod = ""
  let surPeriod = ""
  let hospitalName_tmp = ""
  values?.forEach(v => {
    v.data?.forEach(data => {
      data.values?.forEach(values => {
        if (v.name == "진료기간" && data.length != 0) {
          if (data?.detectedLabel.includes("수술")) {
            surPeriod += values.label
          }
          else {
            diagPeriod += values.label;
          }
        }
        // if((v.name =="입원일자"||v.name =="퇴원일자")&&data.length !=0){
        // }
        if (v.name == "입퇴원일자" && data.length != 0) {
          diagPeriod += values.label;
        }
        if (v.name == "병명코드" && data.length != 0) {
          if (values.label.startsWith("0")) {
            values.label = "D" + values.label.slice(1);
          }
          else if (values.label.startsWith("1")) {
            values.label = "I" + values.label.slice(1);
          }
        }
        //병원명 키워드 기준으로 좌측 값 가져올떄 '병원' 붙이기
        if (v.name == "병원명" && data.direction == "left") {
          hospitalName_tmp += values.label
        }
        if (v.name == "수술일자") {
          if (values?.label.includes("진료기간")) {
            values.label = values.label?.split("진료기간")[0];
          }
        }
        
      })
    })
  })
  diagPeriod = diagPeriod?.replace("상기병명으로인하여", "")

  //입퇴원일자에 진료과가 있는 경우
  const matchdepartment = diagPeriod?.match(/^(\[?[가-힣]+과\])/);
  let department = matchdepartment ? matchdepartment[1] : "";


  //수술명에서 나오는 수술일자들
  let cleanedDates = []

  // 결과 구조 변경
  values = format.setResultFormat(values, keyObj, arrtcd, extractionResultData?.modelmapdata?.category);

  // values = values.filter(value=>
  //   value.extrtItmNm !== '대표자' && value.extrtItmNm !=='전화번호');

  // extractionResultData.extraData = values;

  // 정규식 정의
  const regExp = /[a-zA-Z][0-9]{2,3}([.,:]?[0-9]{1,})?[-0-9]?[0-9]?/g; // 질병분류번호 정규식
  // const regExp = /[a-zA-Z][0-9]{2,4}([.,]?[0-9]{1,4})?([.,]?[0-9]{1,4})?/g; // 질병분류번호 정규식
  const dateExp = /\d{2,4}[년.-/]+\d{0,2}[월.-/]+\d{0,2}(일)?/g;
  const yearExp = /^d{2,4}[년.-/]/g;
  const monthExp = /^\d{0,2}[월.-/]/g;
  const dayExp = /^\d{0,2}(일)/g;
  const licenseExp = /(제)?\d{4,6}(호)?/g;
  const instiExp = /[(]?\d{6,8}[)]?/g;
  const hostExp = /[의병](원)/g;
  const faxExp = /[-/()]{0,2}(FAX).*/g;

  // 정규식 List
  let codeList = [];
  // 환자전화번호
  let telNum = "";
  // 요양기관번호
  let instiNum = "";
  //환자주민번호
  let patientId = "";
  //의사명의 진료과
  let drName_department = ""

  //입원일자, 퇴원일자 관련
  let diagIN = 0
  let diagOUT = 0

  values?.forEach((extrt) => {

    if (extrt?.img_extc_itnm === "병명") {
      let regCode = extrt?.extc_rst_cont01?.match(regExp);
      codeList = regCode;
    }
    // '질병명'에서 질병분류번호 추출
    if (extrt?.img_extc_itnm === "병명") {
      let regCode = extrt?.extc_rst_cont01?.match(regExp);
      codeList = regCode;
    }
    // '임상적추정', '최종진단' 처리
    if (extrt?.img_extc_itnm?.includes("임상적") || extrt?.img_extc_itnm?.includes("최종")) {
      if (extrt?.extrtYn === "Y" && extrt?.extc_rst_cont01?.length > 0) {
        extrt.extc_rst_cont01 = "Y";
      } else if (extrt?.extrtYn === "Y" && extrt?.extc_rst_cont01?.length === 0) {
        extrt.extc_rst_cont01 = "N";
      }
    }

    // 추출값이 있는 경우
    if (extrt?.extc_rst_cont01?.length > 0) {

      // 환자성명
      if (extrt?.img_extc_itnm?.includes("이름")) {
        // 환자주소에 전화번호 값이 있는 경우 추출 후 제거
        if (extrt?.extc_rst_cont01?.includes("전화010")) {
          let splitNum = extrt?.extc_rst_cont01?.split("전화010");
          extrt.extc_rst_cont01 = splitNum[0];
        }
        if (extrt?.extc_rst_cont01?.includes("전화:010")) {
          let splitNum = extrt?.extc_rst_cont01?.split("전화:010");
          extrt.extc_rst_cont01 = splitNum[0];
        }
        // 한글 제외 제거
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[^가-힣]/g, "");
      };

      //주민번호
      if (extrt?.img_extc_itnm?.includes("주민번호")) {
        // 주민번호 뒷자리 7자리 이상일때 자르기
        extrt.extc_rst_cont01 = format.idNumPattern(extrt.extc_rst_cont01)

      };

      // '주소' 
      if (extrt?.img_extc_itnm?.includes("주소")) {
        // [2025-04-17] '주소:'가 있는 경우 제거 (모델 추출)
        if (extrt?.extc_rst_cont01?.includes("주소:")) {
          let eraseAddr = extrt?.extc_rst_cont01?.split("주소:");
          extrt.extc_rst_cont01 = eraseAddr[1];
        }

        // 마지막 값에 '/'가 있는 경우 제거
        if (extrt?.extc_rst_cont01?.includes("/") && extrt?.extc_rst_cont01[extrt?.extc_rst_cont01?.length - 1]?.includes("/")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.slice(0, -1);
        }
        // 시작값에 날짜값이 포함된 경우 제거
        if (yearExp?.test(extrt?.extc_rst_cont01) || monthExp?.test(extrt?.extc_rst_cont01) || dayExp?.test(extrt?.extc_rst_cont01)) {
          const firstData = extrt?.extc_rst_cont01?.slice(0, 6);
          if (yearExp?.test(firstData)) extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(yearExp, "");
          if (monthExp?.test(firstData)) extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(monthExp, "");
          if (dayExp?.test(firstData)) extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(dayExp, "");
        }
        // 오탈자 제거
        if (extrt?.extc_rst_cont01?.includes("전주시I")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace("전주시I", "전주시");
        }

        // 추출값에 날짜패턴이 있는 경우 제거
        if (dateExp?.test(extrt?.extc_rst_cont01)) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(dateExp, "");
        }

        // 환자주소에 전화번호 값이 있는 경우 추출 후 제거
        if (extrt?.img_extc_itnm == ("주소") && (extrt?.extc_rst_cont01?.includes("010") || extrt?.extc_rst_cont01?.includes("전화"))) {
          if (extrt?.extc_rst_cont01?.includes("전화010")) {
            let splitNum = extrt?.extc_rst_cont01?.split("전화010");
            telNum = "010" + splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          if (extrt?.extc_rst_cont01?.includes("언락처")) {
            let splitNum = extrt?.extc_rst_cont01?.split("(언락처)");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          if (extrt?.extc_rst_cont01?.includes("전화번호:")) {
            let splitNum = extrt?.extc_rst_cont01?.split("전화번호:");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          else if (extrt?.extc_rst_cont01?.includes("전화번호")) {
            let splitNum = extrt?.extc_rst_cont01?.split("전화번호");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          if (extrt?.extc_rst_cont01?.includes("전화:")) {
            let splitNum = extrt?.extc_rst_cont01?.split("전화:");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          if (extrt?.extc_rst_cont01?.includes("(전화)")) {
            let splitNum = extrt?.extc_rst_cont01?.split("(전화)");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
          if (extrt?.extc_rst_cont01?.includes("[전화]")) {
            let splitNum = extrt?.extc_rst_cont01?.split("[전화]");
            telNum = splitNum[1];
            extrt.extc_rst_cont01 = splitNum[0];
          }
        }
      }

      // '전화번호'
      if (extrt?.img_extc_itnm?.includes("연락처")) {
        if (extrt?.img_extc_itnm?.includes("환자")) {
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01.replace(/[\\(\\)]/g, "");
        } else {
          let matchData = extrt?.extc_rst_cont01?.match(faxExp);
          if (matchData !== null) {
            extrt.extc_rst_cont01 = extrt.extc_rst_cont01.replace(matchData[0], "");
          }

        }
        // '()' 제거
        if (extrt?.extc_rst_cont01?.includes("()")) {
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01.replace(/[\\(\\)]/g, "");
        }
        //병원연락처에 Fax 번호까지 나왔을 때 
        if (extrt?.img_extc_itnm?.includes("병원")) {
          const re = /\(\d{2,3}\)\d{3,4}-\d{4}/g;
          if (typeof extrt.extc_rst_cont01 === "string" && extrt.extc_rst_cont01.length > 14) {
            const matches = extrt.extc_rst_cont01.match(re);
            if (matches && matches.length > 0) {
              extrt.extc_rst_cont01 = matches[0];
            }
          }
        }

      }

      // '질병분류번호'에 날짜값 있을 경우 제거
      if (extrt?.img_extc_itnm?.includes("병명코드")) {
        if (dateExp?.test(extrt?.extc_rst_cont01)) {
          const removeExp = /(2)(0)\d{1,2}.[년./-]\d{1,2}.[월./-]\d{1,2}.*/g;
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(removeExp, "");
        }
        // 한글 제거
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[가-힣]/g, "");
        // ','를 '.'로 치환
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[,]/g, ".");
      }

      // '면허번호'
      if (extrt?.img_extc_itnm?.includes("면허번호")) {
        // '제, 호, 숫자'가 아닌 경우 제거
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[^0-9]/g, "");

        // // '제'만 있고 '호'가 없을 경우, 추가
        // if (extrt?.extc_rst_cont01?.includes("제") && !extrt?.extc_rst_cont01?.includes("호")) {
        //   extrt.extc_rst_cont01 = extrt?.extc_rst_cont01 + "호";
        // }

        // // '호'만 있고'제'가 없을 경우, 추가
        // if (extrt?.extc_rst_cont01?.includes("호") && !extrt?.extc_rst_cont01?.includes("제")) {
        //   extrt.extc_rst_cont01 = "제" + extrt?.extc_rst_cont01;
        // }
      }

      // '의료기관_이름' 오탈자 수정
      if (extrt?.img_extc_itnm?.includes("병원명")) {
        if (extrt?.extc_rst_cont01?.includes("의과의원")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace("의과의원", "외과의원");
        }
        if (extrt?.extc_rst_cont01?.includes("명칭")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/(명칭)[:]/g, "");
        }
        // 명칭에 날짜패턴이 있는 경우 제거
        if (extrt?.extc_rst_cont01?.includes("년") && extrt?.extc_rst_cont01?.includes("일")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(dateExp, "");
        }
        // ...() 뒤에 의미없는 추가값이 있는 경우 제거
        if (extrt?.extc_rst_cont01?.includes(")(")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[)]+[(]+[0-9]/g, ")");
        }
        // 요양기관번호 추출 후 제거
        if (instiExp?.test(extrt?.extc_rst_cont01)) {
          instiNum = extrt?.extc_rst_cont01?.match(instiExp)[0];
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(instiExp, "");
        }
        //병으로만 끝날때 원 추가
        if (extrt.extc_rst_cont01 && extrt.extc_rst_cont01.slice(-1) == "병") {
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01 + "원"

        }
        if (extrt?.extc_rst_cont01?.includes("(직인")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/(\(직인)/g, "");
        }
        // '의원' 또는 '병원'이 마지막 글자가 아니고 이후 글자가 긴 경우, 도장으로 간주하여 제거
        if (hostExp?.test(extrt?.extc_rst_cont01)) {
          let hostData = extrt?.extc_rst_cont01?.split("병원");
          if (hostData?.length < 2) hostData = extrt?.extc_rst_cont01?.split("의원");
          if (hostData?.length > 1 && hostData[hostData?.length - 1]?.length > 5) {
            extrt.extc_rst_cont01 = extrt.extc_rst_cont01?.replace(hostData[hostData?.length - 1], "");
          }
        }
        //병원명 키워드 기준으로 좌측 값 가져올떄 '병원' 붙이기
        if (hospitalName_tmp) {
          extrt.extc_rst_cont01 = hospitalName_tmp + "병원"
        }
      }

      // '날짜' 관련 항목
      if (extrt?.img_extc_itnm?.includes("일")) {
        // 영어 제거
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[a-zA-Z]/g, "");
        // '년월및' -> '년월일' 수정
        if (extrt?.extc_rst_cont01?.includes("년월및")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace("년월및", "년월일");
        }
        // '이상' -> '미상' 치환
        if (extrt?.extc_rst_cont01?.includes("이상")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace("이상", "미상");
        }
        // '법월일부터' -> '년월일부터' 수정
        if (extrt?.extc_rst_cont01?.includes("법월일부터")) {
          extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace("법월일부터", "년월일부터");
        }
      }

      // '의사성명'
      if (extrt?.img_extc_itnm?.includes("의사명")) {
        let drName = extrt.extc_rst_cont01
        // 면허번호 정규식 일치값 제거
        drName = drName?.replace(licenseExp, "");
        // 한글 제외 제거
        drName = drName?.replace(/[^가-힣]/g, "");
        if (drName.length % 2 === 0) {
          const half = drName.length / 2;
          const first = drName.slice(0, half);
          const second = drName.slice(half);

          if (first === second) {
            drName = first;
          }
        }
        //중복 제거 후에도 5글자 이상이면 앞 3글자만
        if (drName.length >= 5) {
          //의사명에 진료과까지 있는경우
          if (drName.includes("과")) {
            const splitIdx = drName.indexOf("과");
            // const before = drName.slice(0, splitIdx+1);
            const after = drName.slice(splitIdx + 1).trim();

            if (after.length <= 4 && after.length > 0) {
              drName_department = drName.slice(0, splitIdx + 1);
              drName = after
            }
            else {
              drName = drName
            }
          }
          else drName = drName.slice(0, 3);
        }
        //4글자 + 마지막이 '인'이면 '인' 제거
        if (drName.length === 4 && drName.endsWith("인")) {
          drName = drName.slice(0, 3);
        }
        extrt.extc_rst_cont01 = drName;
      }

      // 결과값의 첫글자가 ":"인 경우 제거
      if (extrt?.extc_rst_cont01[0]?.includes(":")) {
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.slice(1);
      }

      //환자 주민번호 patientId 에 저장
      if (extrt?.img_extc_itnm?.includes("주민번호")) {
        patientId = extrt.extc_rst_cont01
      }
      //성별 '남/여'로 통일
      if (extrt?.img_extc_itnm?.includes("성별")) {
        let gender = extrt?.extc_rst_cont01 ?? "";
        const malePatterns = ["남", "남자", "man", "male", "m", "M"];
        const femalePatterns = ["여", "여자", "woman", "female", "f", "F"];
        if (malePatterns.some(p => gender === p || gender.includes(p))) {
          extrt.extc_rst_cont01 = "남";
        } else if (femalePatterns.some(p => gender === p || gender.includes(p))) {
          extrt.extc_rst_cont01 = "여";
        } else {
          // 매칭 안 되는 경우는 원본 유지 또는 빈값
          // extrt.extc_rst_cont01 = "";
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01;
        }
      }

      //생년월일 YYYYMMDD 맞추기
      if (extrt?.img_extc_itnm?.includes("생년월일")) {
        extrt.extc_rst_cont01 = format.setDateYYYYMMDD(extrt.extc_rst_cont01)
      }
      //연락처 숫자,-,. 외에 제거
      if (extrt?.img_extc_itnm?.includes("연락처")) {
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01
          ?.replace(/[^0-9.\-)\/]/g, "")   // 허용 문자만 남김
          ?.replace(/\)+$/, "");         // 끝에 있는 ) 제거
      }

      //차트번호에 주민등록번호까지 나올때 제거
      if (extrt?.img_extc_itnm?.includes("차트번호")) {
        extrt.extc_rst_cont01 = extrt.extc_rst_cont01
          ?.replace(/[0-9]{6}-[0-9]{7}/g, "")
          ?.trim();
      }

      // //입원일자에 퇴원일자까지 다 나올 경우 분리
      let outdate = ""
      if (extrt?.img_extc_itnm?.includes("입원일자")) {
        const dataP = /[0-9]{8}/g;
        if (extrt.extc_rst_cont01.match(dataP) && extrt.extc_rst_cont01.match(dataP).length == 2) {
          outdate = extrt.extc_rst_cont01.match(dataP)[1]
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01.match(dataP)[0]
        }
      }

      //수술명에서 나온 수술일자
      if (extrt?.img_extc_itnm?.includes("수술명")) {
        const newValues = [];
        // diagPeriod에서 날짜들 미리 뽑아두기 (입/퇴원용)
        const datePattern =
          /(수술일자)?(\d{4}(?:[./-]|년)\d{1,2}(?:[./-]|월)\d{1,2}(?:일)?)/g;

        const datePattern2 = /[0-9]{8}/g;
        let surgeryDates = extrt.extc_rst_cont01.match(datePattern) ?? [];
        if (surgeryDates.length == 0) {
          surgeryDates = extrt.extc_rst_cont01.match(datePattern2) ?? []
        }
        cleanedDates = surgeryDates.map(d =>
          d.replace("수술일자", "")
        );
        extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(datePattern, "")?.replace(datePattern2, "")
      }
      if (extrt?.img_extc_itnm?.includes("수술일자")) {
        const surgeryNm = /수술명.*$/g;
        if (extrt.extc_rst_cont01.match(surgeryNm)) {
          extrt.extc_rst_cont01 = extrt.extc_rst_cont01.replace(surgeryNm, "")
        }

      }
      if (extrt?.img_extc_itnm == "통원일수") {
        extrt.extc_rst_cont01 = extrt.extc_rst_cont01?.replace(/[^0-9]/g, "");
      }

    }

    // ========추출값이 없을 때==========

    //'성별'값이 없어 주민등록번호에서 추출
    if (extrt?.img_extc_itnm?.includes("성별") &&( (extrt?.extc_rst_cont01?.length === 0)||(!["남","여"].includes(extrt.extc_rst_cont01)))) {
      if (typeof patientId === "string" && patientId.includes("-")) {
        const genderDigit = patientId.split("-")[1]?.[0];

        if (genderDigit === "1" || genderDigit === "3" || genderDigit === "5") {
          extrt.extc_rst_cont01 = "남";
        } else if (genderDigit === "2" || genderDigit === "4" || genderDigit === "6") {
          extrt.extc_rst_cont01 = "여";
        }
      }
    }
    //'생년월일'값이 없어 주민등록번호에서 추출
    if (extrt?.img_extc_itnm?.includes("생년월일") && extrt?.extc_rst_cont01?.length === 0) {
      if (typeof patientId === "string") {
        const birthYYMMDD = patientId.split("-")[0]; // YYMMDD
        const normalized = format.setDateFormat(birthYYMMDD);
        if (normalized) extrt.extc_rst_cont01 = normalized;
      }
    }

    if (extrt?.img_extc_itnm?.includes("발급일") && extrt?.extc_rst_cont01?.length === 0) {
      const datePattern =
        /(\d{4}년\d{1,2}월\d{1,2}일|\d{4}[-.]\d{1,2}[-.]\d{1,2}|\d{2}[.]\d{1,2}[.]\d{1,2})/g;
      allText = allText.replace(/\s/g, "");
      const matches = allText.match(datePattern);

      if (matches && matches.length > 0) {
        const lastDateStr = matches[matches.length - 1];

        // 날짜 포맷 통일 
        extrt.extc_rst_cont01 = format.setDateYYYYMMDD(lastDateStr);
      }
    }

    if (extrt?.img_extc_itnm?.includes("입원일자") && extrt?.extc_rst_cont01?.length === 0) {
      diagIN = diagIN + 1
    }
    if (extrt?.img_extc_itnm?.includes("퇴원일자") && extrt?.extc_rst_cont01?.length === 0) {
      diagOUT = diagOUT + 1
    }

    // 입원일자-퇴원일자 없는경우 allText 에서 추출
    const datePattern = '(\\d{4}(?:[./-]|년)\\d{1,2}(?:[./-]|월)\\d{1,2}(?:일)?)';
    const dateRegex = new RegExp(datePattern, 'g');
    const datePeriodPattern = new RegExp(
      `${datePattern}(?:부터|~|-)(~)?(입원)?${datePattern}(?:까지)?`, 'g'
    );
    allText = allText.replace(/\s/g, "");
    const periodMatch = allText.match(datePeriodPattern);
    // if (extrt?.img_extc_itnm?.includes("발급일") && extrt?.extc_rst_cont01?.length === 0) {
    if (periodMatch) {
      const tmp = periodMatch[0]?.match(new RegExp(datePattern, "g"))
      // const startDate = periodMatch[1]; // 첫 날짜
      // const endDate = periodMatch[2];   // 두 번째 날짜
      const startDate = tmp[0] || ""; // 첫 날짜
      const endDate = tmp[1] || "";   // 두 번째 날짜

      if (extrt?.img_extc_itnm?.includes("입원일자") && extrt?.extc_rst_cont01?.length === 0) {
        extrt.extc_rst_cont01 = format.setDateYYYYMMDD(startDate);
      }
      if (extrt?.img_extc_itnm?.includes("퇴원일자") && extrt?.extc_rst_cont01?.length === 0) {
        extrt.extc_rst_cont01 = format.setDateYYYYMMDD(endDate);
      }
    }
    // }
    // 입원일자-퇴원일자 없는경우 진료기간 에서 추출
    // if (diagPeriod) {
    //   const tmp = diagPeriod.match(dateRegex)
    //   if (extrt?.img_extc_itnm?.includes("입원일자") && extrt?.extc_rst_cont01?.length === 0) {

    //     extrt.extc_rst_cont01 = format.setDateYYYYMMDD(tmp[0]);
    //   }
    //   if (extrt?.img_extc_itnm?.includes("퇴원일자") && extrt?.extc_rst_cont01?.length === 0) {
    //     extrt.extc_rst_cont01 = format.setDateYYYYMMDD(tmp[1]);
    //   }
    // }


    // '질병분류번호'에 값이 없고, '질병명'에서 추출된 '질병분류번호'가 있을 경우, 해당 값 대입
    if (extrt?.img_extc_itnm?.includes("병명코드") && extrt?.extc_rst_cont01?.length === 0) {
      if (codeList?.length > 0) extrt.extc_rst_cont01 = codeList?.join('');
    }


    //병명, 병명코드 둘다 코드가 없을때, allcontents 에서 패턴 검색
    if (extrt?.img_extc_itnm?.includes("병명코드") && extrt?.extc_rst_cont01?.length === 0) {
      const text = String(allText ?? "").replace(/\s/g, "");
      const len = text.length;

      // ✅ 10% ~ 70% 구간 계산
      const startIdx = Math.floor(len * 0.10);
      const endIdx = Math.floor(len * 0.70);

      const partialText = text.slice(startIdx, endIdx);
      const matches = partialText.match(/[A-Z][0-9]{2,5}(?:[.:][0-9]{1,2})?/g);
      if (matches && matches.length > 0) {
        const code = matches.join("");
        extrt.extc_rst_cont01 = code;
      }
    }

    // '환자전화번호'에 값이 없고, '환자주소'에서 추출된 '환자전화번호'가 있을 경우, 해당 값 대입
    if (extrt?.img_extc_itnm?.includes("연락처") && extrt?.extc_rst_cont01?.length === 0) {
      if (telNum?.length > 0) extrt.extc_rst_cont01 = telNum;
    }

    // '요양기관기호'에 값이 없고, '의료기관_이름'에서 추출된 '요양기관기호'가 있을 경우, 해당 값 대입
    if (extrt?.img_extc_itnm?.includes("요양기관") && extrt?.extc_rst_cont01?.length === 0) {
      if (instiNum?.length > 0) extrt.extc_rst_cont01 = instiNum;
      // 숫자 제외 제거
      extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/[^0-9]/g, "");
    }

    // '의사면허번호'에 값이 없는 경우, allcontents에 값이 있는지 검색
    if (extrt?.img_extc_itnm?.includes("면허번호") && extrt?.extc_rst_cont01?.length === 0) {
      const licenseFind = /(제)[\s]?\d{4,6}[\s]?(호)/g;
      const licenseFind2 = /\d{4,6}[\s]?(호)/g;
      if (allText?.match(licenseFind) !== null) {
        extrt.extc_rst_cont01 = allText?.match(licenseFind)[0]?.replace(/[\s]/g, "");
      } else if ((allText?.match(licenseFind2) !== null)) {
        extrt.extc_rst_cont01 = allText?.match(licenseFind2)[0]?.replace(/[\s]/g, "");
      }
    }

    if (extrt?.img_extc_itnm?.includes("병원명") && extrt?.extc_rst_cont01?.length === 0) {
      let hospitalIndex = arrtcd.findIndex(v => v.mergetext.includes("병원") && v.iskeyword === false);
      if (hospitalIndex === -1) hospitalIndex = arrtcd.findIndex(v => v.mergetext.includes("의원") && v.iskeyword === false);
      if (hospitalIndex !== -1) {
        let hospitalName = arrtcd[hospitalIndex].mergetext;
        // arrtcd의 mergetext의 마지막 두글자가 병원 or 의원인 경우
        if (hospitalName.substring(arrtcd[hospitalIndex].mergetext.length - 2, arrtcd[hospitalIndex].mergetext.length) === "병원" || hospitalName.substring(arrtcd[hospitalIndex].mergetext.length - 2, arrtcd[hospitalIndex].mergetext.length) === "의원") {
          // '병원 or 의원' 두글자만 추출 된 경우, left 추출값 부여
          if (arrtcd[hospitalIndex].mergetext.length === 2 && arrtcd[hospitalIndex].relation.leftitems.length > 0) {
            let firstLeft = arrtcd[hospitalIndex].coord[0]; // 추출값의 coordinate 0번째 (좌상단 x좌표)
            let secondRight = 0;
            // '병원 or 의원'의 leftitems만큼 순회
            for (let l = 0; l < arrtcd[hospitalIndex].relation.leftitems.length; l++) {
              secondRight = arrtcd[arrtcd[hospitalIndex].relation.leftitems[l].index].coord[6]; // leftitem의 coordinate 6번째 (우상단 x좌표)
              if (Math.abs(secondRight - firstLeft) < 10) {  // 두 좌표 간 거리가 가까우면 text 합치기
                arrtcd[hospitalIndex].mergetext = arrtcd[arrtcd[hospitalIndex].relation.leftitems[l].index].mergetext + arrtcd[hospitalIndex].mergetext;
                firstLeft = arrtcd[arrtcd[hospitalIndex].relation.leftitems[l].index].coord[0];
              } else {  // 거리가 멀면 탈출
                break;
              }
            }
          }
        }
        extrt.extc_rst_cont01 = hospitalName;

        if (extrt?.extc_rst_cont01?.includes("명칭:")) {
          let hospitalSplit = extrt?.extc_rst_cont01?.split("명칭:");
          extrt.extc_rst_cont01 = hospitalSplit[hospitalSplit?.length - 1];
        }
      }
    }
    if (extrt?.img_extc_itnm?.includes("수술일자") && extrt?.extc_rst_cont01?.length === 0) {
      if (cleanedDates.length > 0) {
        const baseSeq = Number.isFinite(extrt.extc_rst_seq)
          ? extrt.extc_rst_seq
          : 0;

        // 0번째는 기존 extrt에 세팅
        extrt.extc_rst_cont01 = format.setDateYYYYMMDD(cleanedDates[0]);
        extrt.extc_rst_seq = baseSeq;

        // // 1번째부터는 복제해서 push
        // for (let i = 1; i < cleanedDates.length; i++) {
        //   resultArr.push({
        //     ...extrt,
        //     extc_rst_seq: baseSeq + i,
        //     extc_rst_cont01: format.setDateYYYYMMDD(cleanedDates[i]),
        //   });
        // }
      }
      else {
        if (surPeriod) {
          extrt.extc_rst_cont01 = format.setDateFormat(surPeriod)

        }
      }
    }
    if (extrt?.img_extc_itnm?.includes("진료과") && extrt?.extc_rst_cont01?.length === 0) {
      if (department) {
        extrt.extc_rst_cont01 = department.replace(/[\[\]]/g, "")
      }
      else {
        const match = diagPeriod?.match(/일간[가-힣]*과/)
        extrt.extc_rst_cont01 = match ? match[0].replace("일간", "") : "";
      }
    }
    if (extrt?.img_extc_itnm?.includes("통원일수") && extrt?.extc_rst_cont01?.length === 0) {
      const datePattern = '(\\d{4}(?:[./-]|년)\\d{1,2}(?:[./-]|월)\\d{1,2}(?:일)?)';
      const dateRegex = new RegExp(datePattern, 'g');
      const datePeriodPattern = new RegExp(
        `(${datePattern})(?:부터|~|-)(?:~)?(통원)(${datePattern})(?:까지)?(?:\\(?\\d+일간\\)?)?`
      );
      const visitdatesPattern = /[0-9]{1,2}(일간)/g
      allText = allText.replace(/\s/g, "");
      const periodMatch = allText?.match(datePeriodPattern) || "";
      const tmp = periodMatch[0]?.match(visitdatesPattern)
      if (tmp) {
        const visitDates = tmp[0] || ""; // 첫 날짜


        extrt.extc_rst_cont01 = visitDates?.replace(/[^0-9]/g, "");
      }
      else extrt.extc_rst_cont01 = ""
    }

    extrt.extc_rst_cont01 = extrt?.extc_rst_cont01?.replace(/\s/g, '');
  });

  values = splitDiagCode(values);
  values = splitMultiValueItem(values, diagPeriod, diagIN, diagOUT);
  values?.forEach(values => {
    if (values?.img_extc_itnm == "통원일" || values?.img_extc_itnm.includes("일자")) {
      values.extc_rst_cont01 = values.extc_rst_cont01?.replace("년월일부터년월일까지", "")
      values.extc_rst_cont01 = values.extc_rst_cont01?.replace(/(\(일\))[-]/g, "")
      if (values.extc_rst_cont01 == "0") {
        values.extc_rst_cont01 = ""
      }
    }
    if (values?.img_extc_itnm == "진료과" && values.extc_rst_cont01.length == 0) {
      values.extc_rst_cont01 = drName_department
    }
  })

  //추출ID, 추출일련번호, 추출항목명, 추출값이 같을때 중복 제거
  const seenFull = new Set()
  const seenSeq = new Set()

  values = values.filter(v => {
    const fullkey = `${v?.extc_itm_no}|${v?.extc_rst_seq}|${v?.img_extc_itnm}|${v?.extc_rst_cont01}`
    const seqkey = `${v?.extc_itm_no}|${v?.extc_rst_seq}|${v?.img_extc_itnm}`
    if (seenFull.has(fullkey)) return false;
    seenFull.add(fullkey);
    if (seenSeq.has(seqkey)) return false;
    seenSeq.add(seqkey);

    return true
  })

  // values = values.filter(v => !(v?.img_extc_itnm == "진료과" && ((v?.extc_rst_seq === 0 && v?.extc_rst_cont01 == "")||!(v?.extc_rst_cont01.endsWith("과")))));
  values = values.filter(v => !(v?.img_extc_itnm == "병명" && /^([.-]\d+)$/.test(v?.v?.extc_rst_cont01 ?? "")))
  // aaron LLM todo
  const viewResult = Object.create(null)
  let opinionMergeText = ""
  let diseaseMergeText = ""

  function parseLLMResult(llmResult) {
    let s = llmResult.trim()
    try {
      const v = JSON.parse(llmResult)
      if (typeof v === "string") {
        const t = v.trim()
        if ((t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]"))) {
          return JSON.parse(t)
        }
      }
      return v
    } catch (error) {
      Logger.error("Parsing Error : @@@@@@@"+ error.message)
    }

    if (s.startsWith('"') && t.endsWith('"')) {
      s = s.slice(1, -1).trim()
    }

    return JSON.parse(s)
  }

  function collectOpinionResult(llmResult) {
    viewResult["소견추출결과"] = parseLLMResult(llmResult)
  }

  function collectDiseaseResult(llmResult) {
    viewResult["병명코드결과"] = parseLLMResult(llmResult)
  }

  for (const value of values) {
    // 의사 소견이 두개 이상의 Object로 들어오지 않는다는 가정
    if (value.img_extc_itnm.includes("소견")) {
      opinionMergeText += (opinionMergeText ? " " : "") + value.extc_rst_cont01
    } else if (value.img_extc_itnm.includes("비고")) {
      opinionMergeText += (opinionMergeText ? " " : "") + value.extc_rst_cont01
    } else if (value.img_extc_itnm === "병명") {
      diseaseMergeText += (diseaseMergeText ? " " : "") + value.extc_rst_cont01
    }
  }

  function buildValues(values, diseaseResult) {
    let seq = 0;

    const emptyCheck = values
      .filter(obj => obj.img_extc_itnm == "병명")
      .every(v => v.extc_rst_cont01 === "")

    const baseTemplate = values.find(v => v.img_extc_itnm == "병명")

    if (!emptyCheck) return values;

    values = values.filter(v => v.img_extc_itnm != "병명")

    const pushItem = (name, type) => {
      values.push({
        ...baseTemplate,
        extc_rst_seq: seq++,
        self_rlbtr_vl: 0.99,
        extc_rst_cont01: name,
        extc_rst_cont10: type || ""
      })
    }

    (diseaseResult["주상병"] ?? []).forEach(name => {
      pushItem(name, "주상병")
    });

    (diseaseResult["부상병"] ?? []).forEach(name => {
      pushItem(name, "부상병")
    });

    (diseaseResult["병명"] ?? []).forEach(name => {
      pushItem(name, "")
    });

    // 병명코드는 llm 적용 안시켜도됨.
    // const codeValue = values.find(v => v.img_extc_itnm === "병명코드")

    // diseaseResult["병명코드"].forEach((llmV, idx) => {
    //   if (llmV == null) return;

    //   const chkValue = values.find(v =>
    //     v.img_extc_itnm === "병명코드" &&
    //     v.extc_rst_seq === idx
    //   )

    //   if (chkValue) {
    //     chkValue.extc_rst_cont01 = llmV
    //   }else {
    //     values.push({
    //       ...codeValue,
    //       extc_rst_seq: idx,
    //       extc_rst_cont01: llmV
    //     })
    //   }
    // })

    return values
  }

  const extractLLM = await llmOpinion.plugin(opinionMergeText)

  const llmResult = extractLLM[0].data[0].values[0].label

  collectOpinionResult(llmResult)

  const opinionResult = viewResult["소견추출결과"]

  // 소건 부분에서는 LLM이 우선이 되어도 됨.
  for (const key of Object.keys(opinionResult)) {
    let llmValue = opinionResult[key]

    if (llmValue.every(v => v != null) && key === "진료과") {
      opinionResult[key] = opinionResult[key].filter(v => v.endsWith("과"))
      llmValue = opinionResult[key]
    }

    if (llmValue.every(v => !v)) continue;

    const baseValue = values.find(v => v.img_extc_itnm === key)

    llmValue.forEach((llmV, idx) => {
      if (llmV == null) return;

      const chkValue = values.find(v =>
        v.img_extc_itnm === key &&
        v.extc_rst_seq === idx
      )
      if (chkValue?.extc_rst_cont01 !== "") {
        return
      } else if (chkValue) {
        chkValue.extc_rst_cont01 = llmV
      } else {
        values.push({
          ...baseValue,
          extc_rst_seq: idx,
          extc_rst_cont01: llmV
        })
      }
    })
  }

  // 1. 2. 3. .. 과 같은 형태 제거 (코드존재하는 .은 제거 안되게 함)
  // const cleanText = diseaseMergeText.replace(/\d+\.(?=[^\d])/g, '')

  // const extractLLM = await llmDiseaseName.plugin(cleanText)

  // const llmResult = extractLLM[0].data[0].values[0].label


  // collectDiseaseResult(llmResult)

  // const diseaseResult = viewResult["병명코드결과"]

  // // llm 출력 결과가 존재하지 않는다면 덮어쓰기 X
  // // llm 출력 결과가 존재한다면,덮어쓰기
  // let filteredDiseaseResult = {}

  // for (const key in diseaseResult) {
  //   const v = diseaseResult[key]

  //   if (v.length < 1 || v == null || v == undefined || v == "") continue;

  //   filteredDiseaseResult[key] = v
  // }

  // if (filteredDiseaseResult != {}) {
  //   values = buildValues(values, filteredDiseaseResult)
  // }

  let patientNm = ""
  let patientAddress = ""
  let tmpYear =''
  values?.forEach((obj) => {
    if(obj?.img_extc_itnm == "진단일"){
      tmpYear= obj.extc_rst_cont01.substr(0,4)
    }
    if(obj?.img_extc_itnm == "발급일" && tmpYear==''){
      tmpYear =obj.extc_rst_cont01.substr(0,4)
    }

    // 날짜 포멧 변경
    if (typeof keyObj["날짜데이터"] !== 'undefined' && keyObj["날짜데이터"]?.length > 0 && keyObj["날짜데이터"]?.indexOf(obj?.img_extc_itnm) >= 0) {
      if (obj.extc_rst_cont01) {
        if (!obj.extc_rst_cont01.includes("년")) {
          obj.extc_rst_cont01 = format.setDateFormat(obj?.extc_rst_cont01)

          if(obj.extc_rst_cont01.length==4){
            obj.extc_rst_cont01 = tmpYear+obj.extc_rst_cont01
          }
          if (obj.extc_rst_cont01.length != 8) {
            obj.extc_rst_cont01 = ""
          }
        }
        else { obj.extc_rst_cont01 = format.setDateFormat(obj?.extc_rst_cont01) }
      }
      if (obj.extc_rst_cont01.length != 8) {
        obj.extc_rst_cont01 = ""
      }
      else obj.extc_rst_cont01 = obj.extc_rst_cont01;
    }
    if (obj?.img_extc_itnm == "차트번호" || obj?.img_extc_itnm == "환자 등록번호") {
      obj.extc_rst_cont01 = obj.extc_rst_cont01?.replace("호:", "")
    }
    if (obj?.img_extc_itnm == "이름") {
      patientNm = obj.extc_rst_cont01
    }
    if (obj?.img_extc_itnm == "주소") {
      patientAddress = obj.extc_rst_cont01
    }
    if (obj?.img_extc_itnm === "병명") {
      obj.extc_rst_cont01 = obj.extc_rst_cont01.replace(/[\.]/g, "")
      obj.extc_rst_cont01 = obj.extc_rst_cont01.replace(/[\(\{\[]]?[A-Za-z]\d{2,5}[\)\}\]]?/g, "")
      obj.extc_rst_cont01 = obj.extc_rst_cont01.replace(/[A-Za-z]\d{2,5}/g, "")
    }
    if (obj.img_extc_itnm == "병명코드") {
      obj.extc_rst_cont01 = obj.extc_rst_cont01.replace(/[^A-Za-z0-9]/g, "")
    }
    if (obj.img_extc_itnm == "수술명") {
      if (obj.extc_rst_cont01 === "수술") {
        obj.extc_rst_cont01 = obj.extc_rst_cont01 = "";
      }
    }
    if (obj.img_extc_itnm == "치료명") {
      if (obj.extc_rst_cont01 === "치료") {
        obj.extc_rst_cont01 = "";
      }
    }
    if (obj.img_extc_itnm == "병원연락처") {
      const phonePattern = /(0\d{1,2}-\d{3,4}-\d{4})/g;
      if (obj.extc_rst_cont01.length > 12) {
        obj.extc_rst_cont01 = obj.extc_rst_cont01?.match(phonePattern)[0];
      }
    }
    //환자 성명이 의사명으로 추출될때 의사명 삭제 (스키마에서 '성명' 으로 잡아서 환자성명이 추출된 case)
    if (obj.img_extc_itnm == "의사명") {
      if (obj.extc_rst_cont01 === patientNm) {
        obj.extc_rst_cont01 = ""
      }
    }
    //환자 주소가 병원주소로 추출될때 의사명 삭제 (스키마에서 '주소' 으로 잡아서 환자주소가 추출된 case)
    if (obj.img_extc_itnm == "병원 주소") {
      if (obj.extc_rst_cont01 === patientAddress) {
        obj.extc_rst_cont01 = ""
      }
    }
  });

  // values = format.fillAccidentDate(values)
  // extractionResultData.extraData = values

  const picked = format.fillAccidentDate(values)
  values?.forEach((v) => {
    v.acd_ogtdt = picked
  })
  extractionResultData.result = values


  // extractionResultData.extraData = values;

  // pluginUtil.saveValuesCountToExcel(
  //   extractionResultData?.modelmapdata?.category,
  //   extractionResultData?.modelmapdata?.fileNm,
  //   values.length
  // );

  // 로그 출력
  pluginUtil.printResultLog('', values);
  // pluginUtil.printResultLogExcel('excel', values, extractionResultData, keyObj);

  Logger.debug(`#################### ${extractionResultData?.modelmapdata?.category} Plugin END #################### \t ${extractionResultData.modelmapdata.fileNm}`);

  return extractionResultData;
};

function splitDiagCode(values) {
  const newValues = [];

  values.forEach((item) => {
    if (item?.img_extc_itnm === "병명코드" && item?.extc_rst_cont01) {
      // 1) 영문+숫자만 남기기
      const cleaned = String(item.extc_rst_cont01).replace(/[^A-Za-z0-9]/g, "");

      // 2) "영문 1자리 + 숫자 3~5자리" 단위로 추출 (예: D2420, N608)
      const codeMatches = cleaned.match(/[A-Za-z][0-9]{2,5}/g);

      if (codeMatches?.length) {
        const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

        // ✅ 첫 번째도 교체 (D2420N608 -> D2420)
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: codeMatches[0],
        });

        // ✅ 두 번째부터 새 객체 추가 (seq +1, +2 ...)
        for (let i = 1; i < codeMatches.length; i++) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: codeMatches[i],
          });
        }
        return;
      }
    }

    // 병명코드가 아니거나 매칭이 없으면 그대로
    newValues.push(item);
  });

  return newValues;
}

function splitMultiValueItem(values, diagPeriod, diagIN, diagOUT) {
  const newValues = [];

  // -------------------------
  // 0) diagPeriod 전처리
  // -------------------------
  const dpRaw = String(diagPeriod ?? "");
  const dp = dpRaw.replace(
    /(\d{4}[./-]\d{1,2}[./-]\d{1,2})(?=\d{4}[./-]\d{1,2}[./-]\d{1,2})/g,
    "$1 "
  );

  // 공통: YYYY/MM/DD류 매칭
  const fullDateRegex = /(\d{4}(?:[./-]|년)\d{1,2}(?:[./-]|월)\d{1,2}(?:일)?)/g;

  // 공통: YYMMDD 매칭(200528 같은)
  const yymmddRegex = /\d{6}/g;

  // -------------------------
  // 1) "외래" 뒤 구간에서 날짜 추출 → outpatientDates
  // -------------------------
  let outpatientDates = [];
  const outIdx = dp.indexOf("외래");
  if (outIdx !== -1) {
    const outText = dp.slice(outIdx); // "외래" 이후만

    // 1) YYYY... 먼저
    outpatientDates = outText.match(fullDateRegex) ?? [];

    // 2) 없으면 YYMMDD fallback
    if (outpatientDates.length === 0) {
      const yys = outText.replace(/\s/g, "").match(yymmddRegex) ?? [];
      if (yys.length >= 1) outpatientDates = yys.map(v => format.setDateFormat(v));
    }
  }

  // -------------------------
  // 2) "입원" 뒤 구간에서 날짜 추출 → inoutPairs (입/퇴원 페어)
  // -------------------------
  let inoutDates = [];
  const inIdx = dp.indexOf("입원");
  if (inIdx !== -1) {
    const inText = dp.slice(inIdx); // "입원" 이후만

    // 1) YYYY... 먼저
    inoutDates = inText.match(fullDateRegex) ?? [];

    // 2) 없으면 YYMMDD fallback
    if (inoutDates.length === 0) {
      const yys = inText.replace(/\s/g, "").match(yymmddRegex) ?? [];
      if (yys.length >= 2) inoutDates = yys.map(v => format.setDateFormat(v));
    }
  }
  const inoutPairs = [];
  for (let i = 0; i + 1 < inoutDates.length; i += 2) {
    inoutPairs.push([inoutDates[i], inoutDates[i + 1]]);
  }
  //입퇴원연월일 값에 날짜만 연속 2개인 경우
  if (inoutDates.length == 0 && diagPeriod) {
    if (diagPeriod.match(fullDateRegex)) {
      for (let i = 0; i < diagPeriod.match(fullDateRegex).length; i++) {
        inoutPairs.push([diagPeriod?.match(fullDateRegex)[i], diagPeriod?.match(fullDateRegex)[i + 1]])
        i = i + 1;
      }
    }
  }
  // -------------------------
  // 3) values 순회
  // -------------------------
  values.forEach((item) => {

    // =========================================
    // A) 입원일자 / 퇴원일자: "입원" 뒤 날짜로만 채우기
    // =========================================
    if (
      (item?.img_extc_itnm?.includes("입원일자") || item?.img_extc_itnm?.includes("퇴원일자")) &&
      (diagIN > 0 || diagOUT > 0) &&
      inoutPairs.length > 0
    ) {

      const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

      for (let i = 0; i < inoutPairs.length; i++) {
        const [start, end] = inoutPairs[i];
        const raw = item.img_extc_itnm.includes("입원일자") ? start : end;
        if (start != undefined && end != undefined) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: format.setDateYYYYMMDD(raw),
          });
        }
        // i=i+2
      }
      return;
    }

    // if(item?.img_extc_itnm?.includes("비고") && (item?.extc_rst_cont01?.length ?? 0) > 0){

    // }

    // =========================================
    // B-1) 통원일: item에 값이 있으면 기존 로직(연도 보정 포함)
    // =========================================
    if (item?.img_extc_itnm == "통원일" && (item?.extc_rst_cont01?.length ?? 0) > 0) {
      const raw = item.extc_rst_cont01 ?? "";

      const yearMatch = raw.match(/(\d{4})[./-]\d{1,2}[./-]\d{1,2}/);
      const baseYear = yearMatch ? yearMatch[1] : null;

      const datePattern =
        /(\d{4}[./-]\d{1,2}[./-]\d{1,2})|(\d{1,2}[./-]\d{1,2})/g;

      const matches = raw.match(datePattern) ?? [];

      const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

      // ✅ "애매한 matches"면 가공하지 말고 원본 유지
      const hasHangulYear = raw.includes("년");
      const hasFullYYYY = matches.some(m => /^\d{4}[./-]/.test(m));
      const hasDotToken = matches.some(m => m.includes("."));              // ex) 3.6
      const hasWeirdJoined = matches.some(m => m.includes("/") && m.split("/").length > 2); // ex) 1212/26.28

      const shouldKeepRaw =
        matches.length === 0 ||
        (hasHangulYear && !hasFullYYYY) ||
        hasDotToken ||
        hasWeirdJoined;

      if (shouldKeepRaw) {
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: raw,   // ✅ 무조건 원본 유지
        });
        return;
      }

      // ✅ 여기부터는 "정상 토큰"만 가공
      const normalizedDates = matches
        .map((d) => {
          if (/^\d{4}/.test(d)) return d;
          if (baseYear) return `${baseYear}/${d}`;
          return null;
        })
        .filter(Boolean);

      // normalizedDates가 의미있으면 다건
      if (normalizedDates.length > 0) {
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: format.setDateYYYYMMDD(normalizedDates[0]),
        });

        for (let i = 1; i < normalizedDates.length; i++) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: format.setDateYYYYMMDD(normalizedDates[i]),
          });
        }
        return;
      }

      // 그래도 변환 못 하면 원본 유지
      newValues.push({
        ...item,
        extc_rst_seq: baseSeq,
        extc_rst_cont01: raw,
      });
      return;
    }


    // =========================================
    // B-2) 통원일: item에 값이 없으면 diagPeriod의 "외래" 뒤 날짜로 채우기
    // =========================================
    if (
      item?.img_extc_itnm == ("통원일") &&
      (item?.extc_rst_cont01?.length ?? 0) === 0 &&
      outpatientDates.length > 0
    ) {
      const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

      newValues.push({
        ...item,
        extc_rst_seq: baseSeq,
        extc_rst_cont01: format.setDateYYYYMMDD(outpatientDates[0]),
      });

      for (let i = 1; i < outpatientDates.length; i++) {
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq + i,
          extc_rst_cont01: format.setDateYYYYMMDD(outpatientDates[i]),
        });
      }
      return;
    }

    // =========================================
    // C) 병명 / 진료과: $$$ split
    // =========================================
    if (
      (item?.img_extc_itnm === "병명") &&
      typeof item?.extc_rst_cont01 === "string"
      // && item.extc_rst_cont01.includes("$$$")
    ) {
      Logger.log("======== 병명 ========> "+ item.extc_rst_cont01)
      const parts = item.extc_rst_cont01
        .split("$$$")
        .map(v => v.trim())
        .filter(Boolean);

      const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

      //괄호/대괄호 제거
      const stripBrackets = (s) => String(s ?? "").replace(/[()\[\]]/g, "");
      const compact = (s) => stripBrackets(s).replace(/\s+/g, "");

      //주/부상병판단
      const isMainLabelOnly = (s) => {
        const t = compact(s)
        return t === "주" || t === "주상병" || t === "주질병" || t === "주질병부상"
      }
      const isSubLabelOnly = (s) => {
        const t = compact(s)
        return t === "부" || t === "부상병" || t === "부질병" || t === "부질병부상"
      }

      const normalizeLabel = (inside) => {
        const t = String(inside ?? "").replace(/\s+/g, "")
        if (t === "주" || t === "주상병" || t === "주질병" || t === "주질병부상") return "주상병";
        if (t === "부" || t === "부상병" || t === "부질병" || t === "부질병부상") return "부상병";
        return null;
      }
      const extractLeadingBareLabel = (s) => {
        const raw = String(s ?? "").trim();
        const labels = [
          { key: "주상병", out: "주상병" },
          { key: "주질병", out: "주상병" },
          { key: "주질병부상", out: "주상병" },
          { key: "주", out: "주상병" },
          { key: "부상병", out: "부상병" },
          { key: "부질병", out: "부상병" },
          { key: "부질병부상", out: "부상병" },
          { key: "부", out: "부상병" },
        ];

        for (const { key, out } of labels) {
          if (raw.startsWith(key)) {
            const rest = raw.slice(key.length).replace(/^(\s*[:\-\/]?\s*)/, "").trim()
            if (rest) return { label: out, rest };

            return { label: null, rest: raw }
          }
        }
        return { label: null, rest: raw }
      }

      const extractLabelAnyWherePlusBare = (s) => {
        const raw0 = String(s ?? "").trim();

        const bare = extractLeadingBareLabel(raw0)
        let raw = bare.label ? bare.rest : raw0;
        let label = bare.label || null;

        const bracketRe = /(\(|\[)([^)\]]+)(\)|\])/g;
        const rest = raw.replace(bracketRe, (m, open, inside, close) => {
          const nl = normalizeLabel(inside);
          if (nl) {
            label = nl;
            return ""
          }
          return m;
        }).replace(/\s+/g, " ").trim();
        return { label, rest: rest || raw0 }

      }

      let mode = ""
      let seqOffset = 0;
      for (const p of parts) {
        if (isMainLabelOnly(p)) {
          mode = "주상병"
          continue;
        }
        if (isSubLabelOnly(p)) {
          mode = "부상병"
          continue;
        }
        const { label, rest } = extractLabelAnyWherePlusBare(p);
        const nextMode = label ? label : mode;
        const disease = label ? rest : p;


        const diseaseStr = String(disease ?? "").trim();
        if (!diseaseStr) continue;

        const codeOnlyPattern = /^[A-Za-z]\d{3,5}(?:[A-Z])?$/;
        if (codeOnlyPattern.test(diseaseStr)) {
          continue;
        }

        if (nextMode) mode = nextMode

        newValues.push({
          ...item,
          extc_rst_seq: baseSeq + seqOffset,
          extc_rst_cont01: String(disease).trim(),
          extc_rst_cont10: nextMode || null,
        });
        seqOffset++;
      }
      return;
    }
    if (
      (item?.img_extc_itnm === "진료과") &&
      typeof item?.extc_rst_cont01 === "string" &&
      item.extc_rst_cont01.includes("$$$")
    ) {
      const parts = item.extc_rst_cont01
        .split("$$$")
        .map(v => v.trim())
        .filter(Boolean);

      if (parts.length > 0) {
        const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

        // ✅ 첫 번째도 교체
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: item.img_extc_itnm === "진료과"
            ? parts[0].replace(/과.*$/, "과")
            : parts[0],
        });

        for (let i = 1; i < parts.length; i++) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: item.img_extc_itnm === "진료과"
              ? parts[i].replace(/과.*$/, "과")
              : parts[i],
          });
        }
        return;
      }
    }
    if (
      (item?.img_extc_itnm === "수술일자") &&
      typeof item?.extc_rst_cont01 === "string" &&
      item.extc_rst_cont01.includes("$$$")
    ) {
      const parts = item.extc_rst_cont01
        .split("$$$")
        .map(v => v.trim())
        .filter(Boolean);

      if (parts.length > 0) {
        const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

        // ✅ 첫 번째도 교체
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: parts[0],
        });

        for (let i = 1; i < parts.length; i++) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: parts[i],
          });
        }
        return;
      }
    }
    if (
      (item?.img_extc_itnm === "수술명") &&
      typeof item?.extc_rst_cont01 === "string" &&
      item.extc_rst_cont01.includes("$$$")
    ) {
      const parts = item.extc_rst_cont01
        .split("$$$")
        .map(v => v.trim())
        .filter(Boolean);

      if (parts.length > 0) {
        const baseSeq = Number.isFinite(item.extc_rst_seq) ? item.extc_rst_seq : 0;

        // ✅ 첫 번째도 교체
        newValues.push({
          ...item,
          extc_rst_seq: baseSeq,
          extc_rst_cont01: parts[0],
        });

        for (let i = 1; i < parts.length; i++) {
          newValues.push({
            ...item,
            extc_rst_seq: baseSeq + i,
            extc_rst_cont01: parts[i],
          });
        }
        return;
      }
    }


    // =========================================
    // D) 진료과 후처리
    // =========================================
    if (item?.img_extc_itnm === "진료과" && typeof item?.extc_rst_cont01 === "string") {
      newValues.push({
        ...item,
        extc_rst_cont01: item.extc_rst_cont01.replace(/과.*$/, "과"),
      });
      return;
    }

    newValues.push(item);
  });

  return newValues;
}
